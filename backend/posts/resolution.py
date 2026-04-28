import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Asset, HardClaim, HardClaimEvent


CONTRACT_VERSION = "1.0"


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


def _isoformat_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _due_datetime_utc(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _round_decimal(value: float, places: str = "0.01") -> float:
    return float(Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP))


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
    if not asset.provider_symbol:
        raise ResolutionError(
            "ASSET_PROVIDER_SYMBOL_MISSING",
            "Asset is missing provider lookup metadata.",
        )
    if asset.provider not in Asset.Provider.values:
        raise ResolutionError(
            "UNSUPPORTED_PROVIDER",
            f"Unsupported provider '{asset.provider}'.",
        )
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

def _fetch_coingecko_peak(
    provider_symbol: str, quote_currency: str, from_dt: datetime, to_dt: datetime, direction: str
) -> float:
    """Fetch the highest (bullish) or lowest (bearish) price in the given range."""
    start = int(from_dt.timestamp())
    end = int(to_dt.timestamp())
    params = urlencode({"vs_currency": quote_currency.lower(), "from": start, "to": end})
    url = f"https://api.coingecko.com/api/v3/coins/{provider_symbol}/market_chart/range?{params}"
    payload = _http_get_json(url)
    prices = payload.get("prices")
    if not prices:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "CoinGecko returned no price data for range.")
    values = [float(p[1]) for p in prices]
    return max(values) if direction == "bullish" else min(values)


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


def _fetch_yfinance_peak(
    provider_symbol: str, from_dt: datetime, to_dt: datetime, direction: str
) -> float:
    """Fetch the highest high (bullish) or lowest low (bearish) over the date range."""
    params = urlencode(
        {
            "period1": int(from_dt.timestamp()),
            "period2": int(to_dt.timestamp()),
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
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Yahoo Finance returned no price data for range.")

    indicators = results[0].get("indicators", {})
    quotes = indicators.get("quote") or []
    if not quotes:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", "Yahoo Finance returned no OHLC data for range.")

    key = "high" if direction == "bullish" else "low"
    values = [float(v) for v in (quotes[0].get(key) or []) if v is not None]
    if not values:
        raise ResolutionError("PROVIDER_NO_PRICE_DATA", f"Yahoo Finance returned no {key} prices for range.")
    return max(values) if direction == "bullish" else min(values)


def fetch_price_for_time(instrument: dict[str, Any], at_dt: datetime) -> tuple[float, str]:
    provider = instrument["provider"]
    provider_symbol = instrument["provider_symbol"]
    quote_currency = instrument["quote_currency"]

    if provider == Asset.Provider.COINGECKO:
        return _fetch_coingecko_price(provider_symbol, quote_currency, at_dt)
    if provider == Asset.Provider.YFINANCE:
        return _fetch_yfinance_price(provider_symbol, at_dt)

    raise ResolutionError("UNSUPPORTED_PROVIDER", f"Provider '{provider}' is not supported.")


def fetch_peak_price(
    instrument: dict[str, Any], from_dt: datetime, to_dt: datetime, direction: str
) -> float:
    """Fetch the most favorable price in [from_dt, to_dt] for the given direction."""
    provider = instrument["provider"]
    provider_symbol = instrument["provider_symbol"]
    quote_currency = instrument["quote_currency"]

    if provider == Asset.Provider.COINGECKO:
        return _fetch_coingecko_peak(provider_symbol, quote_currency, from_dt, to_dt, direction)
    if provider == Asset.Provider.YFINANCE:
        return _fetch_yfinance_peak(provider_symbol, from_dt, to_dt, direction)

    raise ResolutionError("UNSUPPORTED_PROVIDER", f"Provider '{provider}' is not supported.")


def fetch_reference_price(resolution_request: dict[str, Any]) -> tuple[float, str]:
    reference_at = datetime.fromisoformat(
        resolution_request["reference_at"].replace("Z", "+00:00")
    )
    return fetch_price_for_time(resolution_request["instrument"], reference_at)


def fetch_due_price(resolution_request: dict[str, Any]) -> tuple[float, str]:
    due_at = datetime.fromisoformat(resolution_request["due_at"].replace("Z", "+00:00"))
    return fetch_price_for_time(resolution_request["instrument"], due_at)


def evaluate_claim(
    resolution_request: dict[str, Any],
    reference_price: float,
    reference_url: str,
    due_price: float,
    due_url: str,
    peak_price: float,
) -> dict[str, Any]:
    target = resolution_request["target"]
    if target["kind"] != "percentage":
        raise ResolutionError(
            "NOT_IMPLEMENTED_FOR_STORED_CLAIMS",
            "Exact-price resolution is not implemented for stored claims yet.",
        )

    if reference_price <= 0:
        raise ResolutionError(
            "INVALID_REFERENCE_PRICE",
            "Reference price must be greater than zero.",
        )

    change_pct = ((peak_price - reference_price) / reference_price) * 100
    threshold = float(target["value"])
    direction = target["direction"]

    if direction == "bullish":
        confirmed = change_pct >= threshold
        reason = (
            "peak price met or exceeded bullish percentage target within timeframe"
            if confirmed
            else "peak price did not reach bullish percentage target within timeframe"
        )
    else:
        confirmed = change_pct <= (-threshold)
        reason = (
            "trough price met or exceeded bearish percentage target within timeframe"
            if confirmed
            else "trough price did not reach bearish percentage target within timeframe"
        )

    return {
        "version": CONTRACT_VERSION,
        "claim_id": resolution_request["claim_id"],
        "resolvable": True,
        "resolved": True,
        "status": HardClaim.Status.CONFIRMED if confirmed else HardClaim.Status.REJECTED,
        "instrument": {
            "symbol": resolution_request["instrument"]["symbol"],
            "provider": resolution_request["instrument"]["provider"],
            "provider_symbol": resolution_request["instrument"]["provider_symbol"],
        },
        "target": target,
        "prices": {
            "reference": _round_decimal(reference_price),
            "reference_url": reference_url,
            "due": _round_decimal(due_price),
            "due_url": due_url,
            "peak": _round_decimal(peak_price),
            "currency": resolution_request["instrument"]["quote_currency"],
        },
        "computed_change_pct": _round_decimal(change_pct),
        "evaluation_reason": reason,
        "resolved_at": _isoformat_utc(datetime.now(timezone.utc)),
    }


def preview_resolution(hard_claim: HardClaim) -> dict[str, Any]:
    resolution_request = normalize_claim_for_resolution(hard_claim)
    reference_price, reference_url = fetch_reference_price(resolution_request)
    due_price, due_url = fetch_due_price(resolution_request)
    direction = resolution_request["target"]["direction"]
    reference_at = datetime.fromisoformat(
        resolution_request["reference_at"].replace("Z", "+00:00")
    )
    due_at = datetime.fromisoformat(
        resolution_request["due_at"].replace("Z", "+00:00")
    )
    peak_price = fetch_peak_price(
        resolution_request["instrument"], reference_at, due_at, direction
    )
    return evaluate_claim(resolution_request, reference_price, reference_url, due_price, due_url, peak_price)


def resolve_hard_claim(hard_claim: HardClaim) -> dict[str, Any]:
    result = preview_resolution(hard_claim)
    hard_claim.status = result["status"]
    hard_claim.save(update_fields=["status"])
    
    HardClaimEvent.objects.create(
        hard_claim=hard_claim,
        event_type=HardClaimEvent.EventType.RESOLUTION,
        details={
            "prices": result["prices"],
            "computed_change_pct": result["computed_change_pct"],
            "evaluation_reason": result["evaluation_reason"]
        }
    )
    return result
