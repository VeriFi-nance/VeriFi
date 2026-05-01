"""
Claim resolution engine — OHLC-based daily analysis.

Fetches the reference price at exact created_at timestamp (preserving existing
behaviour), then performs day-by-day high/low checks against the computed target
price using cached OHLC candle data.
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
from .ohlc_fetcher import OHLCFetchError, get_ohlc_data

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


def _round_decimal(value: float, places: str = "0.01") -> float:
    return float(Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP))


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
    day_start = datetime.combine(at_dt.date(), time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    params = urlencode(
        {
            "period1": int(day_start.timestamp()),
            "period2": int(day_end.timestamp()),
            "interval": "1d",
            "includePrePost": "false",
            "events": "history",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{provider_symbol}?{params}"
    payload = _http_get_json(url)
    chart = payload.get("chart", {})
    results = chart.get("result") or []
    if not results:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Yahoo Finance returned no price data.")

    indicators = results[0].get("indicators", {})
    quotes = indicators.get("quote") or []
    closes = quotes[0].get("close") if quotes else None
    if not closes:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Yahoo Finance returned no closing price.")

    for close in closes:
        if close is not None:
            return float(close), url
    raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Yahoo Finance returned only null close prices.")


def _fetch_binance_price(symbol: str, at_dt: datetime) -> tuple[float, str]:
    """Fetch the close price of the daily candle containing at_dt from Binance."""
    day_start_ms = int(datetime.combine(at_dt.date(), time.min, tzinfo=timezone.utc).timestamp() * 1000)
    day_end_ms = int(datetime.combine(at_dt.date(), time.max, tzinfo=timezone.utc).timestamp() * 1000)
    params = urlencode({"symbol": symbol, "interval": "1d", "startTime": day_start_ms, "endTime": day_end_ms, "limit": 1})
    url = f"https://api.binance.com/api/v3/klines?{params}"
    payload = _http_get_json(url)
    if not payload:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Binance returned no kline data.")
    # Use the open price if at_dt is at the start of the day, otherwise use close
    candle = payload[0]
    return float(candle[4]), url  # close price


def fetch_reference_price(hard_claim: HardClaim) -> tuple[float, str]:
    """
    Fetch the price at the exact created_at timestamp.
    Routes based on asset type: crypto → Binance / CoinGecko, traditional → Yahoo Finance.
    """
    asset = hard_claim.asset
    at_dt = hard_claim.created_at

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


# ---------------------------------------------------------------------------
# Claim validation
# ---------------------------------------------------------------------------

def normalize_claim_for_resolution(hard_claim: HardClaim) -> dict[str, Any]:
    if hard_claim.status != HardClaim.Status.UNDETERMINED:
        raise ResolutionError("CLAIM_ALREADY_RESOLVED", "Claim is already resolved.")

    due_at = _due_datetime_utc(hard_claim.until)
    now = datetime.now(timezone.utc)
    if due_at > now:
        raise ResolutionError(
            "CLAIM_NOT_DUE",
            "Claim cannot be resolved before its due date.",
        )

    asset = hard_claim.asset
    if hard_claim.direction.lower() not in {"bullish", "bearish"}:
        raise ResolutionError(
            "UNSUPPORTED_DIRECTION",
            "Only bullish and bearish percentage claims are supported.",
        )

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
            "kind": "percentage",
            "direction": hard_claim.direction.lower(),
            "value": float(hard_claim.percentage),
            "unit": "percent",
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
    Day-by-day scan of OHLC data to detect target price breaches.

    Returns a full resolution result dict including:
    - target_price, hit_days, target_reached_at, closest_price
    - status (confirmed / rejected)
    - ohlc data for chart rendering
    """
    direction = hard_claim.direction.lower()
    percentage = float(hard_claim.percentage)

    if reference_price <= 0:
        raise ResolutionError("INVALID_REFERENCE_PRICE", "Reference price must be greater than zero.")

    # Compute target price
    if direction == "bullish":
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
                hit_days.append(candle.date.isoformat())
                if first_hit_date is None:
                    first_hit_date = candle.date.isoformat()
            # Track closest approach via high
            distance = abs(candle.high - target_price)
            if distance < closest_distance:
                closest_distance = distance
                closest_price = candle.high
        else:
            # Bearish: check if low reached or went below target
            if candle.low <= target_price:
                hit_days.append(candle.date.isoformat())
                if first_hit_date is None:
                    first_hit_date = candle.date.isoformat()
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
            f"price {'met or exceeded' if direction == 'bullish' else 'fell to or below'} "
            f"target on {len(hit_days)} day(s) within timeframe"
        )
    else:
        reason = (
            f"price did not {'reach' if direction == 'bullish' else 'fall to'} "
            f"target within timeframe"
        )

    # Build OHLC array for chart
    ohlc_list = [
        {
            "date": c.date.isoformat(),
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
            "kind": "percentage",
            "direction": direction,
            "value": percentage,
            "unit": "percent",
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

def preview_resolution(hard_claim: HardClaim) -> dict[str, Any]:
    """Validate and compute resolution without saving."""
    normalize_claim_for_resolution(hard_claim)

    # 1. Reference price at created_at
    reference_price, reference_url = fetch_reference_price(hard_claim)

    # 2. Load OHLC data for the claim period
    start_date = hard_claim.created_at.date()
    end_date = hard_claim.until
    ohlc_rows = get_ohlc_data(hard_claim.asset, start_date, end_date)

    if not ohlc_rows:
        raise ResolutionError("NO_OHLC_DATA", "Could not obtain any OHLC data for the claim period.")

    # 3. Evaluate
    return _evaluate_ohlc(hard_claim, reference_price, reference_url, ohlc_rows)


def resolve_hard_claim(hard_claim: HardClaim) -> dict[str, Any]:
    """Resolve a claim and save the result to DB."""
    result = preview_resolution(hard_claim)

    # Update claim status
    hard_claim.status = result["status"]
    hard_claim.save(update_fields=["status"])

    # Create resolution event with enriched details
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
    return result
