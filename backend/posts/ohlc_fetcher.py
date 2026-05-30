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


def _assert_aligned(dt: datetime, interval: Interval):
    """
    Enforces that when querying in uniform resolution mode (mixed_resolution=False),
    the developer passes datetime inputs that align exactly with the candle boundaries 
    of the chosen interval (e.g., 00:00:00 UTC for daily candles).
    """
    if interval == Interval.ONE_DAY:
        if not (dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0):
            raise AssertionError(f"datetime {dt} is not aligned with ONE_DAY boundary (needs to be 00:00:00 UTC)")
    elif interval == Interval.ONE_HOUR:
        if not (dt.minute == 0 and dt.second == 0 and dt.microsecond == 0):
            raise AssertionError(f"datetime {dt} is not aligned with ONE_HOUR boundary")
    elif interval == Interval.FIFTEEN_MIN:
        if not (dt.minute % 15 == 0 and dt.second == 0 and dt.microsecond == 0):
            raise AssertionError(f"datetime {dt} is not aligned with FIFTEEN_MIN boundary")
    elif interval == Interval.ONE_MIN:
        if not (dt.second == 0 and dt.microsecond == 0):
            raise AssertionError(f"datetime {dt} is not aligned with ONE_MIN boundary")


def _ensure_daily_cached(asset: Asset, start_time: datetime, end_time: datetime):
    """
    Ensures that the 1d (daily) candles for all dates covering the range [start_time, end_time]
    are present in the database. When mixed_resolution=True, this pass is executed first
    to establish basic daily cache coverage for the entire query period.
    
    IMPORTANT: This function should only be called with start_time and end_time that are 
    strictly aligned with daily boundaries (00:00:00 UTC).
    """
    _assert_aligned(start_time, Interval.ONE_DAY)
    _assert_aligned(end_time, Interval.ONE_DAY)
    
    existing = list(OHLCData.objects.filter(
        asset=asset,
        timestamp__gte=start_time,
        timestamp__lte=end_time + timedelta(days=1) - timedelta(microseconds=1),
        interval=Interval.ONE_DAY.value
    ))
    from collections import Counter
    date_counts = Counter(row.timestamp for row in existing)
    
    all_dts = set()
    current = start_time
    while current <= end_time:
        all_dts.add(current)
        current += timedelta(days=1)
        
    today_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    missing_dts = set()
    for dt in all_dts:
        if dt == today_dt or date_counts[dt] == 0:
            missing_dts.add(dt)
            
    if missing_dts:
        min_dt = min(missing_dts)
        max_dt = max(missing_dts) + timedelta(days=1) - timedelta(microseconds=1)
        try:
            fetched = fetch_ohlc_for_asset(asset, min_dt, max_dt, Interval.ONE_DAY)
            new_rows = [
                OHLCData(
                    asset=asset,
                    timestamp=row["timestamp"],
                    interval=Interval.ONE_DAY.value,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"]
                )
                for row in fetched
                if row["timestamp"] in missing_dts
            ]
            if new_rows:
                OHLCData.objects.bulk_create(new_rows, ignore_conflicts=True)
        except OHLCFetchError:
            logger.warning("Could not fetch missing daily OHLC data for %s (%s -> %s)", asset.symbol, min_dt, max_dt)
            raise


def _ensure_interval_cached(asset: Asset, start_time: datetime, end_time: datetime, interval: Interval):
    """
    Used ONLY when mixed_resolution=False (uniform resolution queries, e.g., for charting).
    Checks cache completeness at the daily granularity: for each date in the range, it counts
    cached candles and compares against the expected count (e.g. 24 hourly candles per day).
    If any day has missing candles, it fetches the entire day from the API.
    """
    start_day = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
    existing = list(OHLCData.objects.filter(
        asset=asset,
        timestamp__gte=start_day,
        timestamp__lte=end_day + timedelta(days=1) - timedelta(microseconds=1),
        interval=interval.value
    ))
    from collections import Counter
    date_counts = Counter(row.timestamp.replace(hour=0, minute=0, second=0, microsecond=0) for row in existing)
    
    all_dts = set()
    current = start_day
    while current <= end_day:
        all_dts.add(current)
        current += timedelta(days=1)
        
    today_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    missing_dts = set()
    expected_crypto_counts = {
        Interval.ONE_DAY.value: 1,
        Interval.ONE_HOUR.value: 24,
        Interval.FIFTEEN_MIN.value: 96,
        Interval.ONE_MIN.value: 1440
    }
    
    for dt in all_dts:
        if dt == today_dt:
            missing_dts.add(dt)
        elif asset.market_type == Asset.MarketType.CRYPTO and interval.value != Interval.ONE_DAY.value:
            if date_counts[dt] < expected_crypto_counts.get(interval.value, 1):
                missing_dts.add(dt)
        elif date_counts[dt] == 0:
            missing_dts.add(dt)
            
    if missing_dts:
        min_dt = min(missing_dts)
        max_dt = max(missing_dts) + timedelta(days=1) - timedelta(microseconds=1)
        try:
            fetched = fetch_ohlc_for_asset(asset, min_dt, max_dt, interval)
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
                if row["timestamp"].replace(hour=0, minute=0, second=0, microsecond=0) in missing_dts
            ]
            if new_rows:
                OHLCData.objects.bulk_create(new_rows, ignore_conflicts=True)
        except OHLCFetchError:
            logger.warning("Could not fetch missing OHLC data for %s (%s -> %s) at interval %s", asset.symbol, min_dt, max_dt, interval.name)
            raise


def _ensure_sub_day_cached(asset: Asset, sub_start: R1mDateTime, sub_end: R1mDateTime, interval: Interval):
    """
    Used ONLY when mixed_resolution=True (multi-resolution queries, e.g., for position resolution boundaries).
    Checks cache completeness for specific intraday segments (e.g. 18:00 to 24:00 on the creation day).
    Unlike _ensure_interval_cached, it cannot check daily counts because the range is only a partial day.
    Instead, it calculates the exact list of expected timestamps, checks if they exist in the DB,
    identifies the missing sub-range, and fetches/caches them.
    """
    duration_map = {
        Interval.ONE_HOUR: timedelta(hours=1),
        Interval.FIFTEEN_MIN: timedelta(minutes=15),
        Interval.ONE_MIN: timedelta(minutes=1)
    }
    duration = duration_map[interval]
    
    expected_timestamps = []
    curr = sub_start
    while curr < sub_end:
        expected_timestamps.append(curr)
        curr += duration
        
    if not expected_timestamps:
        return
        
    existing_timestamps = set(OHLCData.objects.filter(
        asset=asset,
        timestamp__in=expected_timestamps,
        interval=interval.value
    ).values_list('timestamp', flat=True))
    
    missing_timestamps = [ts for ts in expected_timestamps if ts not in existing_timestamps]
    
    if missing_timestamps:
        min_missing = min(missing_timestamps)
        max_missing = max(missing_timestamps)
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
                if row["timestamp"] in missing_timestamps
            ]
            if new_rows:
                OHLCData.objects.bulk_create(new_rows, ignore_conflicts=True)
        except OHLCFetchError:
            logger.warning("Could not fetch missing sub-day OHLC data for %s (%s -> %s) at interval %s", asset.symbol, min_missing, max_missing, interval.name)
            raise


def _partition_range(start_time: R1mDateTime, end_time: R1mDateTime) -> list[tuple[R1mDateTime, R1mDateTime, Interval]]:
    """
    Partitions the [start_time, end_time] range into optimal, non-overlapping chunks.
    It uses a greedy algorithm starting from the beginning of the range:
    It tries to fit the largest possible interval (1d -> 1h -> 15m -> 1m) that is:
      1. Aligned to the start boundary of that interval.
      2. Does not exceed end_time.
    This guarantees that boundaries (like start day and end day) use fine resolution 
    where alignment requires it, while intermediate days use daily resolution.
    
    Assumes start_time and end_time are already strictly 1-minute aligned.
    """
    if not (start_time.second == 0 and start_time.microsecond == 0):
        raise ValueError(f"start_time {start_time} is not aligned to 1-minute boundary")
    if not (end_time.second == 0 and end_time.microsecond == 0):
        raise ValueError(f"end_time {end_time} is not aligned to 1-minute boundary")

    INTERVAL_SPECS = [
        (Interval.ONE_DAY, timedelta(days=1), lambda dt: dt.hour == 0 and dt.minute == 0),
        (Interval.ONE_HOUR, timedelta(hours=1), lambda dt: dt.minute == 0),
        (Interval.FIFTEEN_MIN, timedelta(minutes=15), lambda dt: dt.minute % 15 == 0),
        (Interval.ONE_MIN, timedelta(minutes=1), lambda dt: True),
    ]
    
    chunks = []
    current = start_time
    while current < end_time:
        selected = False
        for interval, duration, align_check in INTERVAL_SPECS:
            if align_check(current) and current + duration <= end_time:
                chunks.append((current, current + duration, interval))
                current += duration
                selected = True
                break
        if not selected:
            break
            
    return chunks


def _merge_chunks(chunks: list[tuple[R1mDateTime, R1mDateTime, Interval]]) -> list[tuple[R1mDateTime, R1mDateTime, Interval]]:
    """
    Cooperates with _partition_range to optimize API requests.
    _partition_range outputs many small adjacent chunks of the same resolution (e.g. six 1-hour chunks).
    If we fetched these individually, it would result in six separate API requests.
    This function merges adjacent chunks of the same interval (e.g., merging six 1-hour chunks
    into a single 6-hour range [18:00, 24:00)), so we only make one API call to cache the range.
    """
    if not chunks:
        return []
    merged = []
    current_start, current_end, current_interval = chunks[0]
    for next_start, next_end, next_interval in chunks[1:]:
        if next_interval == current_interval and next_start == current_end:
            current_end = next_end
        else:
            merged.append((current_start, current_end, current_interval))
            current_start, current_end, current_interval = next_start, next_end, next_interval
    merged.append((current_start, current_end, current_interval))
    return merged


def get_ohlc_data(
    asset: Asset, 
    start_time: datetime, 
    end_time: datetime, 
    interval: Interval = Interval.ONE_DAY, 
    mixed_resolution: bool = False
) -> list[OHLCData]:
    """
    Main router to fetch and query OHLC data from the database cache.
    
    If mixed_resolution=False:
      - Validates and enforces alignment assertions for the start and end datetimes.
      - Checks cache completeness at daily granularity and returns a list of candles of uniform resolution.
      
    If mixed_resolution=True:
      - Normalizes boundaries (rounds start_time UP to prevent past leakage, end_time DOWN to prevent future leakage).
      - Ensures all 1d daily candles are cached for basic daily coverage.
      - Partitions the range into non-overlapping resolution segments (1d, 1h, 15m, 1m).
      - Consolidates contiguous segments to perform bulk cache checks and fetch missing sub-day data.
      - Queries and returns the exact non-overlapping sequence covering the range.
    """
    from django.utils.timezone import is_naive, make_aware
    
    if is_naive(start_time):
        start_time = make_aware(start_time, timezone.utc)
    else:
        start_time = start_time.astimezone(timezone.utc)
        
    if is_naive(end_time):
        end_time = make_aware(end_time, timezone.utc)
    else:
        end_time = end_time.astimezone(timezone.utc)

    if not mixed_resolution:
        _assert_aligned(start_time, interval)
        _assert_aligned(end_time, interval)

    start_day = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = end_time.replace(hour=0, minute=0, second=0, microsecond=0)

    _ensure_daily_cached(asset, start_day, end_day)

    if not mixed_resolution:
        _ensure_interval_cached(asset, start_time, end_time, interval)
        return list(OHLCData.objects.filter(
            asset=asset,
            timestamp__gte=start_time,
            timestamp__lte=end_time,
            interval=interval.value
        ).order_by("timestamp"))

    # mixed_resolution = True
    # Convert/round start_time UP and end_time DOWN to R1mDateTime to prevent past/future leakage
    start_time = R1mDateTime.ceil(start_time)
    end_time = R1mDateTime.floor(end_time)

    if start_time >= end_time:
        return []

    chunks = _partition_range(start_time, end_time)
    merged_chunks = _merge_chunks(chunks)

    for sub_start, sub_end, sub_interval in merged_chunks:
        if sub_interval == Interval.ONE_DAY:
            continue
        _ensure_sub_day_cached(asset, sub_start, sub_end, sub_interval)

    result_candles = []
    for sub_start, sub_end, sub_interval in chunks:
        candles = list(OHLCData.objects.filter(
            asset=asset,
            timestamp__gte=sub_start,
            timestamp__lt=sub_end,
            interval=sub_interval.value
        ).order_by("timestamp"))
        result_candles.extend(candles)

    return result_candles
