"""
Claim resolution engine — OHLC-based analysis from claim creation through deadline.

Entry (reference) price is captured at claim creation from an intraday quote at
created_at, stored on HardClaim.reference_price, and reused for charts and resolution.
Target hits are evaluated only on candles at or after created_at (mixed intraday +
daily), so pre-entry moves on the creation day cannot confirm a claim.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Asset, HardClaim, HardClaimEvent, OHLCData
from .ohlc_fetcher import Interval, OHLCFetchError, get_ohlc_data

logger = logging.getLogger(__name__)

CONTRACT_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

@dataclass
class ResolutionError(Exception):
    code: str
    message: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": CONTRACT_VERSION,
            "resolvable": False,
            "resolved": False,
            "error_code": self.code,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _isoformat_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _due_datetime_utc(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _load_claim_ohlc_rows(hard_claim: HardClaim) -> list[OHLCData]:
    """OHLC from created_at through end of until day; no pre-creation leakage."""
    start_time = hard_claim.created_at.astimezone(timezone.utc)
    # Exclusive end at midnight after until so mixed resolution includes the full last day.
    end_time = datetime.combine(
        hard_claim.until + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )
    try:
        return get_ohlc_data(hard_claim.asset, start_time, end_time, mixed_resolution=True)
    except OHLCFetchError as exc:
        # Daily-only fallback: skip the creation calendar day entirely so a full-day
        # bar cannot credit price action that happened before created_at.
        next_day = datetime.combine(
            hard_claim.created_at.date() + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
        if next_day >= end_time:
            raise ResolutionError(
                "NO_OHLC_DATA",
                "Could not obtain intraday OHLC for a same-day claim window.",
            ) from exc
        logger.warning(
            "Mixed OHLC unavailable for claim %s; falling back to daily from %s: %s",
            hard_claim.id,
            next_day.date().isoformat(),
            exc,
        )
        daily_end = datetime.combine(hard_claim.until, time.min, tzinfo=timezone.utc)
        return get_ohlc_data(
            hard_claim.asset,
            next_day,
            daily_end,
            interval=Interval.ONE_DAY,
        )


def _round_decimal(value: float, places: str = "0.01") -> float:
    return float(Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _normalize_direction_and_value_type(
    direction: str | None,
    value_type: str | None,
) -> tuple[str, str]:
    """
    Return consistent (direction, value_type).

    For percentage claims, explicit direction wins over value_type so legacy rows
    with direction=Bearish but value_type=PERCENTAGE_UP still resolve correctly.
    """
    raw = (direction or "").strip().lower()
    vt = (value_type or "").strip().upper() or "PERCENTAGE_UP"

    if vt == "PRICE":
        if raw in {"bullish", "bearish"}:
            return raw, vt
        return "bullish", vt

    if raw == "bearish":
        return "bearish", "PERCENTAGE_DOWN"
    if raw == "bullish":
        return "bullish", "PERCENTAGE_UP"
    if vt == "PERCENTAGE_DOWN":
        return "bearish", "PERCENTAGE_DOWN"
    return "bullish", "PERCENTAGE_UP"


def infer_price_direction(hard_claim: HardClaim, target_price: float) -> str:
    """Infer bullish/bearish for absolute price targets from reference vs target."""
    reference = claim_entry_price(hard_claim)
    if reference is not None:
        if target_price < reference * 0.995:
            return "bearish"
        if target_price > reference * 1.005:
            return "bullish"

    raw = (hard_claim.direction or "").strip().lower()
    if raw in {"bullish", "bearish"}:
        return raw
    return "bullish"


def reconcile_claim_fields(hard_claim: HardClaim) -> tuple[str, str]:
    """
    Normalize direction/value_type and fix common legacy mistakes:
    - large magnitudes stored as percentage moves → PRICE
    - PRICE targets with direction opposite to reference → corrected
    """
    direction, value_type = _normalize_direction_and_value_type(
        hard_claim.direction,
        hard_claim.value_type,
    )
    pct = float(hard_claim.percentage)

    if value_type in {"PERCENTAGE_UP", "PERCENTAGE_DOWN"} and pct > 150:
        value_type = "PRICE"

    if value_type == "PRICE":
        direction = infer_price_direction(hard_claim, pct)

    return direction, value_type


def reference_price_for_display(hard_claim: HardClaim) -> float | None:
    """Best-effort entry price for UI labels."""
    return claim_entry_price(hard_claim)


def claim_entry_price(hard_claim: HardClaim) -> float | None:
    """Entry price locked at creation; falls back for legacy rows only."""
    if hard_claim.reference_price is not None:
        return float(hard_claim.reference_price)

    creation = next(
        (e for e in hard_claim.events.all() if e.event_type == HardClaimEvent.EventType.CREATION),
        None
    )
    if creation and creation.details:
        stored = creation.details.get("reference_price")
        if stored is not None:
            return float(stored)

    resolution = next(
        (e for e in hard_claim.events.all() if e.event_type == HardClaimEvent.EventType.RESOLUTION),
        None
    )
    if resolution and resolution.details:
        prices = resolution.details.get("prices", {})
        stored = prices.get("reference")
        if stored is not None:
            return float(stored)

    # Do not make synchronous network requests during serialization.
    # Legacy claims that lack a reference_price will just return None.
    return None


def claim_target_price(hard_claim: HardClaim, entry: float | None = None) -> float | None:
    """Target price derived from entry and claim magnitude."""
    entry = claim_entry_price(hard_claim) if entry is None else entry
    if entry is None or entry <= 0:
        return None

    direction, value_type = reconcile_claim_fields(hard_claim)
    magnitude = float(hard_claim.percentage)
    if value_type == "PRICE":
        return _round_decimal(magnitude)
    if direction == "bullish":
        return _round_decimal(entry * (1 + magnitude / 100))
    return _round_decimal(entry * (1 - magnitude / 100))


def display_percentage(hard_claim: HardClaim) -> float | None:
    """Percentage magnitude for compact UI (converts absolute PRICE targets)."""
    direction, value_type = reconcile_claim_fields(hard_claim)
    magnitude = float(hard_claim.percentage)

    if value_type != "PRICE":
        return round(magnitude, 1)

    reference = reference_price_for_display(hard_claim)
    if reference is None or reference <= 0:
        return None

    if direction == "bullish":
        return round((magnitude - reference) / reference * 100, 1)
    return round((reference - magnitude) / reference * 100, 1)


def _effective_direction(hard_claim: HardClaim) -> str:
    """Return bullish or bearish for resolution."""
    direction, _ = reconcile_claim_fields(hard_claim)
    return direction


# ---------------------------------------------------------------------------
# Reference-price fetchers (single timestamp lookups — kept from old system)
# ---------------------------------------------------------------------------

def _http_get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "VeriFi/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ResolutionError("PROVIDER_HTTP_ERROR", f"Provider returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise ResolutionError("PROVIDER_NETWORK_ERROR", "Provider network request failed.") from exc
    except json.JSONDecodeError as exc:
        raise ResolutionError("PROVIDER_INVALID_JSON", "Provider returned malformed JSON.") from exc


def _fetch_coingecko_price(provider_symbol: str, quote_currency: str, at_dt: datetime) -> tuple[float, str]:
    start = int((at_dt - timedelta(hours=12)).timestamp())
    end = int((at_dt + timedelta(hours=12)).timestamp())
    params = urlencode({"vs_currency": quote_currency.lower(), "from": start, "to": end})
    url = f"https://api.coingecko.com/api/v3/coins/{provider_symbol}/market_chart/range?{params}"
    payload = _http_get_json(url)
    prices = payload.get("prices")
    if not prices:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "CoinGecko returned no price data.")
    nearest = min(prices, key=lambda item: abs((item[0] / 1000) - at_dt.timestamp()))
    return float(nearest[1]), url


def _fetch_yfinance_price(provider_symbol: str, at_dt: datetime) -> tuple[float, str]:
    at_dt = at_dt.astimezone(timezone.utc).replace(microsecond=0)
    period1 = int((at_dt - timedelta(minutes=10)).timestamp())
    period2 = int((at_dt + timedelta(minutes=10)).timestamp())
    params = urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1m",
            "includePrePost": "false",
            "events": "history",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{provider_symbol}?{params}"
    payload = _http_get_json(url)
    chart = payload.get("chart", {})
    results = chart.get("result") or []
    if not results:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Yahoo Finance returned no chart data.")

    result = results[0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators", {})
    quotes = indicators.get("quote") or []
    closes = quotes[0].get("close") if quotes else None
    if not timestamps or not closes:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Yahoo Finance returned no intraday prices.")

    target_ts = at_dt.timestamp()
    best_idx = None
    best_delta = None
    for idx, (ts, close) in enumerate(zip(timestamps, closes)):
        if close is None:
            continue
        delta = abs(ts - target_ts)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_idx = idx

    if best_idx is None:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Yahoo Finance returned only null close prices.")

    return float(closes[best_idx]), url


def _fetch_binance_price(symbol: str, at_dt: datetime) -> tuple[float, str]:
    """Fetch BTC/USDT-style price at at_dt using the 1m kline containing that instant."""
    at_dt = at_dt.astimezone(timezone.utc).replace(microsecond=0)
    minute_start = at_dt.replace(second=0)
    start_ms = int(minute_start.timestamp() * 1000)
    end_ms = start_ms + 60_000 - 1
    params = urlencode(
        {
            "symbol": symbol,
            "interval": "1m",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1,
        }
    )
    url = f"https://api.binance.com/api/v3/klines?{params}"
    payload = _http_get_json(url)
    if not payload:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Binance returned no kline data.")

    candle = payload[0]
    open_price = float(candle[1])
    close_price = float(candle[4])
    seconds_into_minute = (at_dt - minute_start).total_seconds()
    if seconds_into_minute <= 0:
        return open_price, url
    if seconds_into_minute >= 60:
        return close_price, url
    fraction = seconds_into_minute / 60.0
    return open_price + (close_price - open_price) * fraction, url


def fetch_current_price(asset: Asset, at_dt: datetime) -> tuple[float, str]:
    """Fetch the price for an asset at a specific datetime."""
    if asset.market_type == Asset.MarketType.CRYPTO:
        # Try Binance first, then CoinGecko
        if asset.binance_symbol:
            try:
                return _fetch_binance_price(asset.binance_symbol, at_dt)
            except ResolutionError:
                pass
        if asset.provider_symbol:
            try:
                return _fetch_coingecko_price(asset.provider_symbol, asset.quote_currency, at_dt)
            except ResolutionError:
                pass
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Could not fetch reference price from any crypto source.")
    else:
        # Traditional: Yahoo Finance, then try with twelvedata_symbol on Yahoo
        if asset.provider_symbol:
            try:
                return _fetch_yfinance_price(asset.provider_symbol, at_dt)
            except ResolutionError:
                pass
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Could not fetch reference price from any traditional source.")

def fetch_reference_price(hard_claim: HardClaim) -> tuple[float, str]:
    """
    Return the entry price captured at claim creation, or fetch it for legacy rows.
    """
    if hard_claim.reference_price is not None:
        return float(hard_claim.reference_price), hard_claim.reference_price_url or "stored_at_creation"
    return fetch_current_price(hard_claim.asset, hard_claim.created_at)


def capture_reference_price(hard_claim: HardClaim) -> HardClaim:
    """Fetch spot price at created_at and persist on the claim."""
    price, url = fetch_current_price(hard_claim.asset, hard_claim.created_at)
    rounded = _round_decimal(price)
    hard_claim.reference_price = rounded
    hard_claim.reference_price_url = url
    hard_claim.save(update_fields=["reference_price", "reference_price_url"])

    creation_event = hard_claim.events.filter(event_type=HardClaimEvent.EventType.CREATION).first()
    if creation_event is not None:
        details = dict(creation_event.details or {})
        details["reference_price"] = rounded
        details["reference_url"] = url
        details["reference_at"] = _isoformat_utc(hard_claim.created_at)
        creation_event.details = details
        creation_event.save(update_fields=["details"])

    return hard_claim


# ---------------------------------------------------------------------------
# Claim validation
# ---------------------------------------------------------------------------

def normalize_claim_for_resolution(
    hard_claim: HardClaim,
    *,
    allow_resolved: bool = False,
) -> dict[str, Any]:
    if not allow_resolved and hard_claim.status != HardClaim.Status.UNDETERMINED:
        raise ResolutionError("CLAIM_ALREADY_RESOLVED", "Claim is already resolved.")

    due_at = _due_datetime_utc(hard_claim.until)
    now = datetime.now(timezone.utc)
    if due_at > now:
        raise ResolutionError(
            "CLAIM_NOT_DUE",
            "Claim cannot be resolved before its due date.",
        )

    asset = hard_claim.asset
    raw_direction = (hard_claim.direction or "").strip().lower()
    if raw_direction and raw_direction not in {"bullish", "bearish"}:
        raise ResolutionError(
            "UNSUPPORTED_DIRECTION",
            "Only bullish and bearish percentage claims are supported.",
        )
    direction = _effective_direction(hard_claim)
    _, value_type = reconcile_claim_fields(hard_claim)

    return {
        "version": CONTRACT_VERSION,
        "claim_id": hard_claim.id,
        "instrument": {
            "symbol": asset.symbol,
            "market_type": asset.market_type,
            "provider": asset.provider,
            "provider_symbol": asset.provider_symbol,
            "quote_currency": asset.quote_currency,
        },
        "target": {
            "kind": "price" if value_type == "PRICE" else "percentage",
            "direction": direction,
            "value": float(hard_claim.percentage),
            "unit": asset.quote_currency if value_type == "PRICE" else "percent",
        },
        "reference_at": _isoformat_utc(hard_claim.created_at),
        "due_at": _isoformat_utc(due_at),
    }


# ---------------------------------------------------------------------------
# OHLC-based evaluation
# ---------------------------------------------------------------------------

def _evaluate_ohlc(
    hard_claim: HardClaim,
    reference_price: float,
    reference_url: str,
    ohlc_rows: list[OHLCData],
) -> dict[str, Any]:
    """
    Scan OHLC candles (post-creation) to detect target price breaches.

    Returns a full resolution result dict including:
    - target_price, hit_days, target_reached_at, closest_price
    - status (confirmed / rejected)
    - ohlc data for chart rendering
    """
    direction = _effective_direction(hard_claim)
    _, value_type = reconcile_claim_fields(hard_claim)
    percentage = float(hard_claim.percentage)

    if reference_price <= 0:
        raise ResolutionError("INVALID_REFERENCE_PRICE", "Reference price must be greater than zero.")

    # Compute target price
    if value_type == "PRICE":
        target_price = percentage
    elif direction == "bullish":
        target_price = reference_price * (1 + percentage / 100)
    else:
        target_price = reference_price * (1 - percentage / 100)

    # Day-by-day analysis
    hit_days: list[str] = []
    first_hit_date: str | None = None
    closest_price: float | None = None
    closest_distance = float("inf")

    for candle in ohlc_rows:
        if direction == "bullish":
            # Check if high reached or exceeded target
            if candle.high >= target_price:
                hit_days.append(candle.timestamp.date().isoformat())
                if first_hit_date is None:
                    first_hit_date = candle.timestamp.date().isoformat()
            # Track closest approach via high
            distance = abs(candle.high - target_price)
            if distance < closest_distance:
                closest_distance = distance
                closest_price = candle.high
        else:
            # Bearish: check if low reached or went below target
            if candle.low <= target_price:
                hit_days.append(candle.timestamp.date().isoformat())
                if first_hit_date is None:
                    first_hit_date = candle.timestamp.date().isoformat()
            # Track closest approach via low
            distance = abs(candle.low - target_price)
            if distance < closest_distance:
                closest_distance = distance
                closest_price = candle.low

    confirmed = len(hit_days) > 0

    # Due price = last candle's close (the deadline day)
    due_price = ohlc_rows[-1].close if ohlc_rows else reference_price

    # Peak price for backward compat
    if direction == "bullish":
        peak_price = max(c.high for c in ohlc_rows) if ohlc_rows else reference_price
    else:
        peak_price = min(c.low for c in ohlc_rows) if ohlc_rows else reference_price

    change_pct = ((peak_price - reference_price) / reference_price) * 100

    if confirmed:
        reason = (
            f"Claim price {'met or exceeded' if direction == 'bullish' else 'fell to or below'} "
            f"target on {len(hit_days)} day(s) within timeframe"
        )
    else:
        reason = (
            f"Claim price did not {'reach' if direction == 'bullish' else 'fall to'} "
            f"target within timeframe"
        )

    # Build OHLC array for chart
    ohlc_list = [
        {
            "date": c.timestamp.date().isoformat(),
            "open": _round_decimal(c.open),
            "high": _round_decimal(c.high),
            "low": _round_decimal(c.low),
            "close": _round_decimal(c.close),
        }
        for c in ohlc_rows
    ]

    return {
        "version": CONTRACT_VERSION,
        "claim_id": hard_claim.id,
        "resolvable": True,
        "resolved": True,
        "status": HardClaim.Status.CONFIRMED if confirmed else HardClaim.Status.REJECTED,
        "instrument": {
            "symbol": hard_claim.asset.symbol,
            "provider": hard_claim.asset.provider,
            "provider_symbol": hard_claim.asset.provider_symbol,
        },
        "target": {
            "kind": "price" if hard_claim.value_type == "PRICE" else "percentage",
            "direction": direction,
            "value": percentage,
            "unit": hard_claim.asset.quote_currency if hard_claim.value_type == "PRICE" else "percent",
        },
        "prices": {
            "reference": _round_decimal(reference_price),
            "reference_url": reference_url,
            "due": _round_decimal(due_price),
            "due_url": "",
            "peak": _round_decimal(peak_price),
            "target": _round_decimal(target_price),
            "closest": _round_decimal(closest_price) if closest_price is not None else None,
            "currency": hard_claim.asset.quote_currency,
        },
        "computed_change_pct": _round_decimal(change_pct),
        "evaluation_reason": reason,
        "target_reached_at": first_hit_date,
        "hit_days": hit_days,
        "ohlc": ohlc_list,
        "resolved_at": _isoformat_utc(datetime.now(timezone.utc)),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preview_resolution(hard_claim: HardClaim, *, allow_resolved: bool = False) -> dict[str, Any]:
    """Validate and compute resolution without saving."""
    normalize_claim_for_resolution(hard_claim, allow_resolved=allow_resolved)

    # 1. Load OHLC from claim creation through deadline (mixed intraday + daily).
    try:
        ohlc_rows = _load_claim_ohlc_rows(hard_claim)
    except ResolutionError:
        raise
    except OHLCFetchError as exc:
        raise ResolutionError("NO_OHLC_DATA", str(exc)) from exc

    if not ohlc_rows:
        raise ResolutionError("NO_OHLC_DATA", "Could not obtain any OHLC data for the claim period.")

    # 2. Reference price locked at claim creation (fallback for legacy claims)
    try:
        reference_price, reference_url = fetch_reference_price(hard_claim)
        if hard_claim.reference_price is None:
            hard_claim.reference_price = _round_decimal(reference_price)
            hard_claim.reference_price_url = reference_url
            hard_claim.save(update_fields=["reference_price", "reference_price_url"])
    except ResolutionError:
        # Fallback to the first in-window candle open if APIs fail.
        reference_price = float(ohlc_rows[0].open)
        reference_url = "fallback_ohlc_open"

    # 3. Evaluate
    return _evaluate_ohlc(hard_claim, reference_price, reference_url, ohlc_rows)


def _persist_resolution_result(
    hard_claim: HardClaim,
    result: dict[str, Any],
    *,
    replace_existing_event: bool = False,
) -> None:
    hard_claim.status = result["status"]
    hard_claim.save(update_fields=["status"])

    if replace_existing_event:
        hard_claim.events.filter(event_type=HardClaimEvent.EventType.RESOLUTION).delete()

    HardClaimEvent.objects.create(
        hard_claim=hard_claim,
        event_type=HardClaimEvent.EventType.RESOLUTION,
        details={
            "prices": result["prices"],
            "computed_change_pct": result["computed_change_pct"],
            "evaluation_reason": result["evaluation_reason"],
            "target_reached_at": result["target_reached_at"],
            "hit_days": result["hit_days"],
        },
    )


def _maybe_settle_rep_market(hard_claim: HardClaim) -> None:
    if hard_claim.status not in (HardClaim.Status.CONFIRMED, HardClaim.Status.REJECTED):
        return
    try:
        market = hard_claim.market
    except HardClaim.market.RelatedObjectDoesNotExist:
        return
    if market is None or market.resolved:
        return
    from .rep_market import resolve as resolve_market

    winning_side = "YES" if hard_claim.status == HardClaim.Status.CONFIRMED else "NO"
    resolve_market(market, winning_side)


def resolve_hard_claim(hard_claim: HardClaim) -> dict[str, Any]:
    """Resolve a claim and save the result to DB."""
    result = preview_resolution(hard_claim)
    _persist_resolution_result(hard_claim, result)
    _maybe_settle_rep_market(hard_claim)
    return result


def resolve_hard_claim_observer(hard_claim: HardClaim, now: datetime) -> dict[str, Any] | None:
    """
    Observer-based resolution logic for HardClaims.
    Fetches OHLC data up to min(now, deadline).
    Returns a resolution result (and persists it) if target hit or deadline passed.
    Otherwise returns None (claim remains UNDETERMINED).
    """
    try:
        normalize_claim_for_resolution(hard_claim, allow_resolved=False)
    except ResolutionError as e:
        if e.code == "CLAIM_NOT_DUE":
            pass # We expect it not to be due, we are checking early hits
        else:
            raise

    deadline_utc = _due_datetime_utc(hard_claim.until)
    end_time = min(now, deadline_utc)
    start_time = hard_claim.created_at.astimezone(timezone.utc)

    try:
        ohlc_rows = get_ohlc_data(hard_claim.asset, start_time, end_time, mixed_resolution=True)
    except OHLCFetchError as exc:
        next_day = datetime.combine(
            hard_claim.created_at.date() + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
        if next_day >= end_time:
            logger.warning("No OHLC data for claim %s observer resolution: %s", hard_claim.id, exc)
            if now > deadline_utc:
                raise ResolutionError("NO_OHLC_DATA", "Could not obtain OHLC for expired claim.") from exc
            return None

        daily_end = min(end_time, datetime.combine(hard_claim.until, time.min, tzinfo=timezone.utc))
        try:
            ohlc_rows = get_ohlc_data(
                hard_claim.asset,
                next_day,
                daily_end,
                interval=Interval.ONE_DAY,
            )
        except OHLCFetchError as e:
            logger.warning("Daily fallback failed for claim %s: %s", hard_claim.id, e)
            if now > deadline_utc:
                raise ResolutionError("NO_OHLC_DATA", "Could not obtain daily OHLC for expired claim.") from e
            return None

    if not ohlc_rows:
        if now > deadline_utc:
            raise ResolutionError("NO_OHLC_DATA", "Could not obtain any OHLC data for the claim period.")
        return None

    try:
        reference_price, reference_url = fetch_reference_price(hard_claim)
        if hard_claim.reference_price is None:
            hard_claim.reference_price = _round_decimal(reference_price)
            hard_claim.reference_price_url = reference_url
            hard_claim.save(update_fields=["reference_price", "reference_price_url"])
    except ResolutionError:
        reference_price = float(ohlc_rows[0].open)
        reference_url = "fallback_ohlc_open"

    result = _evaluate_ohlc(hard_claim, reference_price, reference_url, ohlc_rows)

    is_confirmed = result["status"] == HardClaim.Status.CONFIRMED
    is_expired = now > deadline_utc

    if is_confirmed or is_expired:
        _persist_resolution_result(hard_claim, result)
        _maybe_settle_rep_market(hard_claim)
        return result

    return None



def reassess_hard_claim(hard_claim: HardClaim) -> dict[str, Any]:
    """Re-run resolution for an already-settled claim (e.g. after reference_price backfill)."""
    previous_status = hard_claim.status
    result = preview_resolution(hard_claim, allow_resolved=True)
    _persist_resolution_result(hard_claim, result, replace_existing_event=True)
    result["previous_status"] = previous_status
    result["status_changed"] = previous_status != result["status"]
    return result
