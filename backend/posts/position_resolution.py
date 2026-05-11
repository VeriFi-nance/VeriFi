import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone as django_timezone

from .models import Position, PositionEvent
from .ohlc_fetcher import get_ohlc_data, OHLCFetchError
from .resolution import fetch_current_price, ResolutionError

logger = logging.getLogger(__name__)

def calculate_pnl(direction, entry_price, exit_price):
    if direction == Position.Direction.LONG:
        return ((exit_price - entry_price) / entry_price) * 100
    else:  # short
        return ((entry_price - exit_price) / entry_price) * 100

def _round_decimal(value: float, places: str = "0.01") -> float:
    return float(Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP))

def resolve_positions():
    """Run Phase 1 and Phase 2 of position resolution."""
    now = django_timezone.now()
    
    # Phase 1: PENDING -> ACTIVE or MISSED
    pending_positions = Position.objects.filter(status=Position.Status.PENDING)
    for pos in pending_positions:
        try:
            _resolve_pending(pos, now)
        except Exception as e:
            logger.error(f"Error resolving pending position {pos.id}: {e}")

    # Phase 2: ACTIVE -> CONFIRMED, REJECTED, or EXPIRED
    active_positions = Position.objects.filter(status=Position.Status.ACTIVE)
    for pos in active_positions:
        try:
            _resolve_active(pos, now)
        except Exception as e:
            logger.error(f"Error resolving active position {pos.id}: {e}")

def _resolve_pending(pos: Position, now: datetime):
    # OHLC data from creation up to today or entry_interval, whichever is earlier
    end_date = min(now.date(), pos.entry_interval.date())
    
    try:
        ohlc_rows = get_ohlc_data(pos.asset, pos.created_at.date(), end_date)
    except OHLCFetchError:
        return # Skip and retry later
    
    triggered = False
    trigger_date = None
    
    for candle in ohlc_rows:
        if pos.direction == Position.Direction.LONG:
            if candle.low <= pos.entry_price:
                triggered = True
                trigger_date = candle.date
                break
        else: # SHORT
            if candle.high >= pos.entry_price:
                triggered = True
                trigger_date = candle.date
                break
                
    if triggered:
        pos.status = Position.Status.ACTIVE
        pos.save(update_fields=['status'])
        
        # We need to record when it was triggered, possibly updating created_at logic,
        # but since we only have created_at, we will record an event.
        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.ENTRY_TRIGGERED,
            details={"trigger_date": trigger_date.isoformat()}
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
    start_date = pos.created_at.date()
    if trigger_event and "trigger_date" in trigger_event.details:
        start_date = datetime.fromisoformat(trigger_event.details["trigger_date"]).date()
        
    end_date = min(now.date(), pos.lifetime.date())
    
    try:
        ohlc_rows = get_ohlc_data(pos.asset, start_date, end_date)
    except OHLCFetchError:
        return # Skip and retry later

    resolved = False
    exit_price = None
    exit_status = None
    
    for candle in ohlc_rows:
        # Check both SL and TP
        sl_hit = False
        tp_hit = False
        
        if pos.direction == Position.Direction.LONG:
            if candle.low <= pos.stop_loss:
                sl_hit = True
            if candle.high >= pos.take_profit:
                tp_hit = True
        else: # SHORT
            if candle.high >= pos.stop_loss:
                sl_hit = True
            if candle.low <= pos.take_profit:
                tp_hit = True
                
        if sl_hit and tp_hit:
            # Worst case: SL hit
            exit_price = pos.stop_loss
            exit_status = Position.Status.REJECTED
            resolved = True
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
        
        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.RESOLUTION,
            details={"message": f"Position closed via {exit_status}"}
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
