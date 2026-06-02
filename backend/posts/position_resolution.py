import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone as django_timezone

from .models import Position, PositionEvent, OHLCData
from .ohlc_fetcher import get_ohlc_data, OHLCFetchError, Interval
from .resolution import fetch_current_price, ResolutionError

logger = logging.getLogger(__name__)

def calculate_pnl(direction, entry_price, exit_price):
    if direction == Position.Direction.LONG:
        return ((exit_price - entry_price) / entry_price) * 100
    else:  # short
        return ((entry_price - exit_price) / entry_price) * 100

def _round_decimal(value: float, places: str = "0.01") -> float:
    return float(Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP))

def _check_hits(candle, pos: Position) -> tuple[bool, bool]:
    sl_hit = False
    tp_hit = False
    if pos.direction == Position.Direction.LONG:
        if candle.low <= pos.stop_loss:
            sl_hit = True
        if candle.high >= pos.take_profit:
            tp_hit = True
    else:  # SHORT
        if candle.high >= pos.stop_loss:
            sl_hit = True
        if candle.low <= pos.take_profit:
            tp_hit = True
    return sl_hit, tp_hit

def _resolve_ambiguous_candle(pos: Position, target_date) -> tuple[bool, float | None, str | None, bool]:
    """
    Returns (resolved, exit_price, exit_status, is_ambiguous_flag).
    Zoom into 1h -> 15m -> 1m to break ambiguity.
    """
    intervals_to_try = [Interval.ONE_HOUR, Interval.FIFTEEN_MIN, Interval.ONE_MIN]
    
    target_start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    duration_map = {
        Interval.ONE_HOUR: timedelta(hours=23),
        Interval.FIFTEEN_MIN: timedelta(hours=23, minutes=45),
        Interval.ONE_MIN: timedelta(hours=23, minutes=59)
    }
    
    for interval in intervals_to_try:
        try:
            target_end = target_start + duration_map[interval]
            intraday_rows = get_ohlc_data(pos.asset, target_start, target_end, interval)
            for candle in intraday_rows:
                sl_hit, tp_hit = _check_hits(candle, pos)
                if sl_hit and tp_hit:
                    # Still ambiguous at this level! Break inner loop to try next deeper interval.
                    break
                elif sl_hit:
                    return True, pos.stop_loss, Position.Status.REJECTED, False
                elif tp_hit:
                    return True, pos.take_profit, Position.Status.CONFIRMED, False
        except OHLCFetchError:
            logger.warning("Failed to fetch %s data for ambiguity resolution for %s.", interval.name, pos.asset.symbol)
            # Fall through to next interval

    # If exhausted all intervals and still ambiguous, return worst-case SL
    return True, pos.stop_loss, Position.Status.REJECTED, True

def resolve_positions(channel_id: int | None = None):
    """Run Phase 1 and Phase 2 of position resolution.

    Args:
        channel_id: If provided, resolution is scoped to that channel only.
    """
    now = django_timezone.now()

    filters_pending = {"status": Position.Status.PENDING}
    filters_active = {"status": Position.Status.ACTIVE}
    if channel_id is not None:
        filters_pending["channel_id"] = channel_id
        filters_active["channel_id"] = channel_id

    # Phase 1: PENDING -> ACTIVE or MISSED
    for pos in Position.objects.filter(**filters_pending):
        try:
            _resolve_pending(pos, now)
        except Exception as e:
            logger.error(f"Error resolving pending position {pos.id}: {e}")

    # Phase 2: ACTIVE -> CONFIRMED, REJECTED, or EXPIRED
    for pos in Position.objects.filter(**filters_active):
        try:
            _resolve_active(pos, now)
        except Exception as e:
            logger.error(f"Error resolving active position {pos.id}: {e}")

def _resolve_pending(pos: Position, now: datetime):
    # Query window: from position creation up to the entry limit
    end_time = min(now, pos.entry_interval)
    
    try:
        ohlc_rows = get_ohlc_data(pos.asset, pos.created_at, end_time, mixed_resolution=True)
    except OHLCFetchError as e:
        logger.warning(f"Failed to fetch OHLC data for pending position {pos.id}: {e}")
        
        # If expired, we must resolve it now
        if now > pos.entry_interval:
            try:
                # Fallback check: see if the daily price ever hit the entry price
                daily_rows = get_ohlc_data(pos.asset, pos.created_at, end_time, interval=Interval.ONE_DAY, mixed_resolution=False)
                hit_in_daily = False
                for candle in daily_rows:
                    if pos.direction == Position.Direction.LONG:
                        if candle.low <= pos.entry_price:
                            hit_in_daily = True
                            break
                    else:
                        if candle.high >= pos.entry_price:
                            hit_in_daily = True
                            break
                
                if not hit_in_daily:
                    # It was never hit even daily, so it is a standard MISSED position
                    pos.status = Position.Status.MISSED
                    pos.save(update_fields=['status'])
                    PositionEvent.objects.create(
                        position=pos,
                        event_type=PositionEvent.EventType.RESOLUTION,
                        details={"message": "Missed entry price within interval"}
                    )
                    return
            except Exception:
                pass # If daily query also fails, fallback to transition below
            
            # Either it hit in daily (but intraday failed) or we couldn't fetch daily at all.
            # Resolve to MISSED but mark as ambiguous.
            pos.status = Position.Status.MISSED
            pos.save(update_fields=['status'])
            PositionEvent.objects.create(
                position=pos,
                event_type=PositionEvent.EventType.RESOLUTION,
                details={
                    "message": "Missed entry: Trigger occurred on creation day but hourly data was unavailable to resolve time ambiguity.",
                    "ambiguous": True
                }
            )
        return
    
    triggered = False
    trigger_time = None
    
    for candle in ohlc_rows:
        if pos.direction == Position.Direction.LONG:
            if candle.low <= pos.entry_price:
                triggered = True
                trigger_time = candle.timestamp
                break
        else: # SHORT
            if candle.high >= pos.entry_price:
                triggered = True
                trigger_time = candle.timestamp
                break
                
    if triggered:
        pos.status = Position.Status.ACTIVE
        pos.save(update_fields=['status'])
        
        # Record trigger_time as ISO string for the active phase start
        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.ENTRY_TRIGGERED,
            details={"trigger_time": trigger_time.isoformat()}
        )
    elif now > pos.entry_interval:
        # Time ran out, missed entry
        pos.status = Position.Status.MISSED
        pos.save(update_fields=['status'])
        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.RESOLUTION,
            details={"message": "Missed entry price within interval"}
        )

def _resolve_active(pos: Position, now: datetime):
    # Determine when it became active. Find the ENTRY_TRIGGERED event.
    trigger_event = pos.events.filter(event_type=PositionEvent.EventType.ENTRY_TRIGGERED).first()

    if not trigger_event or "trigger_time" not in trigger_event.details:
        raise AssertionError(
            f"The position #{pos.id} you tried to resolve active is still not triggered. You cant resolve_active an untriggered event."
        )
        
    start_time = datetime.fromisoformat(trigger_event.details["trigger_time"])
    end_time = min(now, pos.lifetime)
    
    try:
        ohlc_rows = get_ohlc_data(pos.asset, start_time, end_time, mixed_resolution=True)
    except OHLCFetchError as e:
        logger.warning(f"Failed to fetch OHLC data for active position {pos.id}: {e}")
        # If the lifetime has expired, we must resolve it.
        if now > pos.lifetime:
            try:
                # Try fetching only daily data to check for SL/TP hits
                daily_rows = get_ohlc_data(pos.asset, start_time, end_time, interval=Interval.ONE_DAY, mixed_resolution=False)
                resolved = False
                exit_price = None
                exit_status = None
                ambiguous_flag = False
                
                for candle in daily_rows:
                    sl_hit, tp_hit = _check_hits(candle, pos)
                    if sl_hit and tp_hit:
                        exit_price = pos.stop_loss
                        exit_status = Position.Status.REJECTED
                        resolved = True
                        ambiguous_flag = True
                        break
                    elif sl_hit:
                        exit_price = pos.stop_loss
                        exit_status = Position.Status.REJECTED
                        resolved = True
                        break
                    elif tp_hit:
                        exit_price = pos.take_profit
                        exit_status = Position.Status.CONFIRMED
                        resolved = True
                        break
                
                if resolved:
                    pos.exit_price = exit_price
                    pos.pnl_percentage = calculate_pnl(pos.direction, pos.entry_price, exit_price)
                    pos.status = exit_status
                    pos.save(update_fields=['exit_price', 'pnl_percentage', 'status'])
                    
                    details = {"message": f"Position closed via {exit_status}"}
                    if ambiguous_flag:
                        details["ambiguous"] = True
                    
                    PositionEvent.objects.create(
                        position=pos,
                        event_type=PositionEvent.EventType.RESOLUTION,
                        details=details
                    )
                    return
            except Exception:
                pass # Fall through to closing at latest known price
            
            # If we couldn't resolve via daily check, close at last known price (or current price) as EXPIRED
            exit_price = None
            try:
                cached_daily = OHLCData.objects.filter(
                    asset=pos.asset,
                    timestamp__gte=start_time,
                    timestamp__lte=end_time,
                    interval=Interval.ONE_DAY.value
                ).order_by('timestamp').last()
                if cached_daily:
                    exit_price = cached_daily.close
            except Exception:
                pass
            
            if exit_price is None:
                try:
                    exit_price, _ = fetch_current_price(pos.asset, now)
                except ResolutionError:
                    return # Can't fetch, retry later
            
            pos.exit_price = exit_price
            pos.pnl_percentage = calculate_pnl(pos.direction, pos.entry_price, exit_price)
            pos.status = Position.Status.EXPIRED
            pos.save(update_fields=['exit_price', 'pnl_percentage', 'status'])
            
            PositionEvent.objects.create(
                position=pos,
                event_type=PositionEvent.EventType.RESOLUTION,
                details={
                    "message": "Position expired, closed at market (ambiguous due to fetch failure)",
                    "ambiguous": True
                }
            )
        return

    resolved = False
    exit_price = None
    exit_status = None
    ambiguous_flag = False
    
    for candle in ohlc_rows:
        sl_hit, tp_hit = _check_hits(candle, pos)
                
        if sl_hit and tp_hit:
            # Ambiguous candle! Fallback to higher resolutions.
            target_date = candle.timestamp.date()
            resolved, exit_price, exit_status, ambiguous_flag = _resolve_ambiguous_candle(pos, target_date)
            if resolved:
                break
        elif sl_hit:
            exit_price = pos.stop_loss
            exit_status = Position.Status.REJECTED
            resolved = True
            break
        elif tp_hit:
            exit_price = pos.take_profit
            exit_status = Position.Status.CONFIRMED
            resolved = True
            break

    if resolved:
        pos.exit_price = exit_price
        pos.pnl_percentage = calculate_pnl(pos.direction, pos.entry_price, exit_price)
        pos.status = exit_status
        pos.save(update_fields=['exit_price', 'pnl_percentage', 'status'])
        
        details = {"message": f"Position closed via {exit_status}"}
        if ambiguous_flag:
            details["ambiguous"] = True

        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.RESOLUTION,
            details=details
        )
    elif now > pos.lifetime:
        # Expired. Close at latest known price
        if ohlc_rows:
            exit_price = ohlc_rows[-1].close
        else:
            try:
                exit_price, _ = fetch_current_price(pos.asset, now)
            except ResolutionError:
                return # Can't fetch, retry later
                
        pos.exit_price = exit_price
        pos.pnl_percentage = calculate_pnl(pos.direction, pos.entry_price, exit_price)
        pos.status = Position.Status.EXPIRED
        pos.save(update_fields=['exit_price', 'pnl_percentage', 'status'])
        
        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.RESOLUTION,
            details={"message": "Position expired, closed at market"}
        )

