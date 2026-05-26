"""
OHLC data fetcher with cascading API fallback and DB caching.

Crypto assets:      Binance → Kucoin → Kraken  (no API keys needed)
Traditional assets:  Yahoo Finance v8 → Twelve Data  (Twelve Data needs free API key)
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from .models import Asset, OHLCData

logger = logging.getLogger(__name__)


class R1mDateTime(datetime):
    """
    A subclass of datetime representing a timezone-aware UTC datetime 
    aligned strictly to 1-minute precision (seconds/microseconds set to 0).
    """

    @classmethod
    def floor(cls, dt: datetime) -> R1mDateTime:
        """
        Constructs an R1mDateTime by rounding down (truncating seconds and microseconds).
        Also enforces timezone-aware UTC.
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return cls(dt.year, dt.month, dt.day, dt.hour, dt.minute, tzinfo=dt.tzinfo)

    @classmethod
    def ceil(cls, dt: datetime) -> R1mDateTime:
        """
        Constructs an R1mDateTime by rounding up to the next minute if there are non-zero seconds/microseconds.
        Also enforces timezone-aware UTC.
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
            
        if dt.second > 0 or dt.microsecond > 0:
            dt = dt + timedelta(minutes=1)
            
        return cls(dt.year, dt.month, dt.day, dt.hour, dt.minute, tzinfo=dt.tzinfo)


class OHLCRow(TypedDict):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float


class OHLCFetchError(Exception):
    """Raised when all API sources fail for a given asset type."""
    pass


class Interval(Enum):
    ONE_DAY = "1d"
    ONE_HOUR = "1h"
    FIFTEEN_MIN = "15m"
    ONE_MIN = "1m"


# ---------------------------------------------------------------------------
# Low-level HTTP helper
# ---------------------------------------------------------------------------

def _http_get_json(url: str, timeout: int = 15) -> dict | list:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "VeriFi/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        raise OHLCFetchError(f"HTTP request failed for {url}: {exc}") from exc


# ---------------------------------------------------------------------------
# Crypto fetchers
# ---------------------------------------------------------------------------

def _fetch_binance_ohlc(symbol: str, start: datetime, end: datetime, interval: Interval = Interval.ONE_DAY) -> list[OHLCRow]:
    """
    Binance klines endpoint.  symbol e.g. 'BTCUSDT'.
    Returns OHLC candles in the [start, end] datetime range (inclusive) with intervals.
    Intervals: 1d, 1h, 15m, 1m
    """
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    
    interval_map = {
        Interval.ONE_DAY: "1d",
        Interval.ONE_HOUR: "1h",
        Interval.FIFTEEN_MIN: "15m",
        Interval.ONE_MIN: "1m",
    }
    
    params = urlencode({"symbol": symbol, "interval": interval_map[interval], "startTime": start_ms, "endTime": end_ms, "limit": 1000})
    url = f"https://api.binance.com/api/v3/klines?{params}"
    data = _http_get_json(url)

    rows: list[OHLCRow] = []
    for candle in data:
        # Binance kline: [openTime, open, high, low, close, volume, closeTime, ...]
        open_time_ms = candle[0]
        candle_timestamp = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc)
        rows.append({
            "timestamp": candle_timestamp,
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
        })
    return rows


def _fetch_kucoin_ohlc(symbol: str, start: datetime, end: datetime, interval: Interval = Interval.ONE_DAY) -> list[OHLCRow]:
    """
    Kucoin kline endpoint.  symbol e.g. 'BTC-USDT'.
    Intervals: 1day, 1hour, 15min, 1min
    """
    start_sec = int(start.timestamp())
    end_sec = int(end.timestamp())
    
    interval_map = {
        Interval.ONE_DAY: "1day",
        Interval.ONE_HOUR: "1hour",
        Interval.FIFTEEN_MIN: "15min",
        Interval.ONE_MIN: "1min",
    }
    
    params = urlencode({
        "tradeType": "SPOT",
        "symbol": symbol,
        "interval": interval_map[interval],
        "startAt": start_sec,
        "endAt": end_sec,
    })
    url = f"https://api.kucoin.com/api/ua/v1/market/kline?{params}"
    payload = _http_get_json(url)

    # Kucoin response: {"code": "200000", "data": [[timestamp, open, close, high, low, volume, turnover], ...]}
    candles = payload.get("data", [])
    if not candles:
        raise OHLCFetchError("Kucoin returned no candle data.")

    rows: list[OHLCRow] = []
    for candle in candles:
        candle_timestamp = datetime.fromtimestamp(int(candle[0]), tz=timezone.utc)
        rows.append({
            "timestamp": candle_timestamp,
            "open": float(candle[1]),
            "high": float(candle[3]),
            "low": float(candle[4]),
            "close": float(candle[2]),
        })
    return rows


def _fetch_kraken_ohlc(pair: str, start: datetime, end: datetime, interval: Interval = Interval.ONE_DAY) -> list[OHLCRow]:
    """
    Kraken OHLC endpoint.  pair e.g. 'XBTUSD'.
    Note: Kraken returns up to 720 entries and only recent data.
    Intervals (in minutes): 1440 (1 day), 60 (1 hour), 15, 1
    """
    since_sec = int(start.timestamp())
    
    interval_map = {
        Interval.ONE_DAY: 1440,
        Interval.ONE_HOUR: 60,
        Interval.FIFTEEN_MIN: 15,
        Interval.ONE_MIN: 1,
    }
    
    params = urlencode({"pair": pair, "interval": interval_map[interval], "since": since_sec})
    url = f"https://api.kraken.com/0/public/OHLC?{params}"
    payload = _http_get_json(url)

    errors = payload.get("error", [])
    if errors:
        raise OHLCFetchError(f"Kraken returned errors: {errors}")

    result = payload.get("result", {})
    # Result has the pair key (can vary) and a 'last' key
    candles = []
    for key, value in result.items():
        if key == "last":
            continue
        candles = value
        break

    if not candles:
        raise OHLCFetchError("Kraken returned no candle data.")

    rows: list[OHLCRow] = []
    for candle in candles:
        # Kraken: [time, open, high, low, close, vwap, volume, count]
        candle_timestamp = datetime.fromtimestamp(int(candle[0]), tz=timezone.utc)
        if candle_timestamp > end:
            continue
        rows.append({
            "timestamp": candle_timestamp,
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
        })
    return rows


# ---------------------------------------------------------------------------
# Traditional fetchers (stocks, forex, commodity, index)
# ---------------------------------------------------------------------------

def _fetch_yfinance_ohlc(symbol: str, start: datetime, end: datetime, interval: Interval = Interval.ONE_DAY) -> list[OHLCRow]:
    """
    Yahoo Finance v8 chart API.  symbol e.g. 'AAPL', 'GC=F' (gold futures).
    Intervals: 1d, 1h, 15m, 1m
    """
    period1 = int(start.timestamp())
    period2 = int(end.timestamp())
    
    interval_map = {
        Interval.ONE_DAY: "1d",
        Interval.ONE_HOUR: "1h",
        Interval.FIFTEEN_MIN: "15m",
        Interval.ONE_MIN: "1m",
    }
    
    params = urlencode({
        "period1": period1,
        "period2": period2,
        "interval": interval_map[interval],
        "includePrePost": "false",
        "events": "history",
    })
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{params}"
    payload = _http_get_json(url)

    chart = payload.get("chart", {})
    results = chart.get("result") or []
    if not results:
        raise OHLCFetchError("Yahoo Finance returned no chart data.")

    result = results[0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators", {})
    quotes = indicators.get("quote") or [{}]
    quote = quotes[0]

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []

    rows: list[OHLCRow] = []
    for i, ts in enumerate(timestamps):
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l_ = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        if any(v is None for v in (o, h, l_, c)):
            continue
        candle_timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)
        rows.append({"timestamp": candle_timestamp, "open": float(o), "high": float(h), "low": float(l_), "close": float(c)})
    return rows


def _fetch_twelvedata_ohlc(symbol: str, start: datetime, end: datetime, interval: Interval = Interval.ONE_DAY) -> list[OHLCRow]:
    """
    Twelve Data time_series API.  symbol e.g. 'AAPL', 'XAU/USD'.
    Requires TWELVE_DATA_API_KEY in Django settings.
    Intervals: 1day, 1h, 15min, 1min
    """
    api_key = getattr(settings, "TWELVE_DATA_API_KEY", "")
    if not api_key:
        raise OHLCFetchError("TWELVE_DATA_API_KEY not configured.")

    interval_map = {
        Interval.ONE_DAY: "1day",
        Interval.ONE_HOUR: "1h",
        Interval.FIFTEEN_MIN: "15min",
        Interval.ONE_MIN: "1min",
    }

    params = urlencode({
        "symbol": symbol,
        "interval": interval_map[interval],
        "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": end.strftime("%Y-%m-%d %H:%M:%S"),
        "apikey": api_key,
        "format": "JSON",
        "outputsize": 5000,
    })
    url = f"https://api.twelvedata.com/time_series?{params}"
    payload = _http_get_json(url)

    if payload.get("status") == "error":
        raise OHLCFetchError(f"Twelve Data error: {payload.get('message', 'unknown')}")

    values = payload.get("values") or []
    if not values:
        raise OHLCFetchError("Twelve Data returned no values.")

    rows: list[OHLCRow] = []
    for item in values:
        dt_str = item["datetime"]
        if " " in dt_str:
            candle_timestamp = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        else:
            candle_timestamp = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        rows.append({
            "timestamp": candle_timestamp,
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "close": float(item["close"]),
        })
    return rows


# ---------------------------------------------------------------------------
# Fallback chains
# ---------------------------------------------------------------------------

def _try_crypto_chain(asset: Asset, start: datetime, end: datetime, interval: Interval = Interval.ONE_DAY) -> list[OHLCRow]:
    """Try Binance → Kucoin → Kraken for crypto assets."""
    errors: list[str] = []

    if asset.binance_symbol:
        try:
            logger.info("Trying Binance for %s (%s) [%s]", asset.symbol, asset.binance_symbol, interval.name)
            return _fetch_binance_ohlc(asset.binance_symbol, start, end, interval)
        except OHLCFetchError as e:
            errors.append(f"Binance: {e}")
            logger.warning("Binance failed for %s: %s", asset.symbol, e)

    if asset.kucoin_symbol:
        try:
            logger.info("Trying Kucoin for %s (%s) [%s]", asset.symbol, asset.kucoin_symbol, interval.name)
            return _fetch_kucoin_ohlc(asset.kucoin_symbol, start, end, interval)
        except OHLCFetchError as e:
            errors.append(f"Kucoin: {e}")
            logger.warning("Kucoin failed for %s: %s", asset.symbol, e)

    if asset.kraken_pair:
        try:
            logger.info("Trying Kraken for %s (%s) [%s]", asset.symbol, asset.kraken_pair, interval.name)
            return _fetch_kraken_ohlc(asset.kraken_pair, start, end, interval)
        except OHLCFetchError as e:
            errors.append(f"Kraken: {e}")
            logger.warning("Kraken failed for %s: %s", asset.symbol, e)

    raise OHLCFetchError(f"All crypto OHLC sources failed for {asset.symbol}: {'; '.join(errors)}")


def _try_traditional_chain(asset: Asset, start: datetime, end: datetime, interval: Interval = Interval.ONE_DAY) -> list[OHLCRow]:
    """Try Yahoo Finance → Twelve Data for stocks/forex/commodity/index."""
    errors: list[str] = []

    if asset.provider_symbol:
        try:
            logger.info("Trying Yahoo Finance for %s (%s) [%s]", asset.symbol, asset.provider_symbol, interval.name)
            return _fetch_yfinance_ohlc(asset.provider_symbol, start, end, interval)
        except OHLCFetchError as e:
            errors.append(f"Yahoo Finance: {e}")
            logger.warning("Yahoo Finance failed for %s: %s", asset.symbol, e)

    if asset.twelvedata_symbol:
        try:
            logger.info("Trying Twelve Data for %s (%s) [%s]", asset.symbol, asset.twelvedata_symbol, interval.name)
            return _fetch_twelvedata_ohlc(asset.twelvedata_symbol, start, end, interval)
        except OHLCFetchError as e:
            errors.append(f"Twelve Data: {e}")
            logger.warning("Twelve Data failed for %s: %s", asset.symbol, e)

    raise OHLCFetchError(f"All traditional OHLC sources failed for {asset.symbol}: {'; '.join(errors)}")


# ---------------------------------------------------------------------------
# Router + DB caching
# ---------------------------------------------------------------------------

def fetch_ohlc_for_asset(asset: Asset, start: datetime, end: datetime, interval: Interval = Interval.ONE_DAY) -> list[OHLCRow]:
    """Route to the correct API chain based on asset.market_type."""
    if asset.market_type == Asset.MarketType.CRYPTO:
        return _try_crypto_chain(asset, start, end, interval)
    else:
        return _try_traditional_chain(asset, start, end, interval)


def get_ohlc_data(asset: Asset, start_date: date, end_date: date, interval: Interval = Interval.ONE_DAY) -> list[OHLCData]:
    """
    Get OHLC data for an asset in [start_date, end_date].
    Checks DB first; fetches and caches only missing dates.
    Returns a list of OHLCData model instances ordered by timestamp.
    """
    # For daily intervals, we compare by date.
    # For intraday intervals, we still fetch by date range, but we might want to check existing intervals
    existing = list(OHLCData.objects.filter(
        asset=asset, 
        timestamp__date__gte=start_date, 
        timestamp__date__lte=end_date,
        interval=interval.value
    ))
    
    # Group existing by date to count how many candles we have per day
    from collections import Counter
    date_counts = Counter(row.timestamp.date() for row in existing)

    all_dates = set()
    current = start_date
    while current <= end_date:
        all_dates.add(current)
        current += timedelta(days=1)

    today = datetime.now(timezone.utc).date()
    missing_dates = set()
    
    expected_crypto_counts = {
        Interval.ONE_DAY.value: 1,
        Interval.ONE_HOUR.value: 24,
        Interval.FIFTEEN_MIN.value: 96,
        Interval.ONE_MIN.value: 1440
    }

    for d in all_dates:
        # Always fetch if it's today (day is incomplete)
        if d == today:
            missing_dates.add(d)
        # For past days in crypto, check if we have the full expected candle count
        elif asset.market_type == Asset.MarketType.CRYPTO and interval.value != Interval.ONE_DAY.value:
            if date_counts[d] < expected_crypto_counts.get(interval.value, 1):
                missing_dates.add(d)
        # For non-crypto or daily crypto, just check if we have at least 1 candle
        elif date_counts[d] == 0:
            missing_dates.add(d)

    if missing_dates:
        min_missing = min(missing_dates)
        max_missing = max(missing_dates)
        try:
            fetched = fetch_ohlc_for_asset(asset, min_missing, max_missing, interval)
            new_rows = [
                OHLCData(
                    asset=asset, 
                    timestamp=row["timestamp"], 
                    interval=interval.value,
                    open=row["open"], 
                    high=row["high"], 
                    low=row["low"], 
                    close=row["close"]
                )
                for row in fetched
                if row["timestamp"].date() in missing_dates
            ]
            if new_rows:
                OHLCData.objects.bulk_create(new_rows, ignore_conflicts=True)
        except OHLCFetchError:
            logger.warning("Could not fetch missing OHLC data for %s (%s -> %s) at interval %s", asset.symbol, min_missing, max_missing, interval.name)

    return list(OHLCData.objects.filter(
        asset=asset, 
        timestamp__date__gte=start_date, 
        timestamp__date__lte=end_date,
        interval=interval.value
    ).order_by("timestamp"))
