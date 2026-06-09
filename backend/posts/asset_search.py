"""
Live provider symbol-search for the hybrid asset picker.

Local DB search is the fast path (see AssetListView). When the local catalog
has too few hits for a query, these helpers reach out to external providers
(TwelveData for equities/FX/commodities, CoinGecko for crypto) and return
*candidate* rows that are NOT yet persisted: each has `id: None` and a
`source: "remote"` flag plus the hints (`_market`, `_coingecko_id`,
`quote_currency`) the `/assets/resolve/` endpoint needs to materialize a real
Asset via `asset_providers.get_or_create_asset`.

Hard constraints:
- TwelveData free tier is ~8 req/min, so every remote call is cached
  (short TTL) and any error degrades to an empty list — the picker must never
  block or break on a remote failure.
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_REMOTE_TTL = 60 * 60  # 1h: symbol metadata is effectively static
_HTTP_TIMEOUT = 8


def _http_get_json(url: str) -> Optional[dict | list]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "VeriFi/1.0"})
    try:
        with urlopen(request, timeout=_HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Remote symbol search failed for %s: %s", url, exc)
        return None


def _candidate(*, symbol: str, name: str, market: str, market_type: str,
               quote_currency: str, coingecko_id: Optional[str] = None) -> dict:
    """Shape a remote hit into the picker's candidate contract."""
    return {
        "id": None,
        "source": "remote",
        "symbol": symbol.upper(),
        "name": name,
        "market_type": market_type,
        "quote_currency": quote_currency,
        # Internal hints echoed back by the frontend to /assets/resolve/.
        "_market": market,
        "_coingecko_id": coingecko_id,
    }


# ---------------------------------------------------------------------------
# TwelveData (equities, FX, commodities)
# ---------------------------------------------------------------------------

# instrument_type -> (our market, MarketType value)
_TD_TYPE_MAP = {
    "common stock": ("nasdaq", "equity"),
    "stock": ("nasdaq", "equity"),
    "etf": ("nasdaq", "equity"),
    "physical currency": ("forex", "forex"),
    "digital currency": ("crypto", "crypto"),
}


def _twelvedata_search(query: str, limit: int) -> list[dict]:
    api_key = getattr(settings, "TWELVE_DATA_API_KEY", "")
    if not api_key:
        return []
    params = urlencode({"symbol": query, "outputsize": min(limit * 3, 30), "apikey": api_key})
    payload = _http_get_json(f"https://api.twelvedata.com/symbol_search?{params}")
    if not isinstance(payload, dict):
        return []
    out: list[dict] = []
    for item in payload.get("data", []) or []:
        symbol = (item.get("symbol") or "").strip()
        if not symbol:
            continue
        exchange = (item.get("exchange") or "").upper()
        country = (item.get("country") or "").lower()
        itype = (item.get("instrument_type") or "").lower()
        market, market_type = _TD_TYPE_MAP.get(itype, ("nasdaq", "equity"))
        # Borsa Istanbul overrides the equity default.
        if exchange in ("BIST", "BORSA ISTANBUL") or country in ("turkey", "türkiye"):
            market, market_type = "bist", "equity"
        out.append(_candidate(
            symbol=symbol,
            name=item.get("instrument_name") or symbol,
            market=market,
            market_type=market_type,
            quote_currency=(item.get("currency") or ("TRY" if market == "bist" else "USD")).upper(),
        ))
    return out


# ---------------------------------------------------------------------------
# CoinGecko (crypto)
# ---------------------------------------------------------------------------

def _coingecko_search(query: str, limit: int) -> list[dict]:
    params = urlencode({"query": query})
    payload = _http_get_json(f"https://api.coingecko.com/api/v3/search?{params}")
    if not isinstance(payload, dict):
        return []
    out: list[dict] = []
    for coin in (payload.get("coins") or [])[: limit * 2]:
        symbol = (coin.get("symbol") or "").strip()
        cg_id = (coin.get("id") or "").strip()
        if not symbol or not cg_id:
            continue
        out.append(_candidate(
            symbol=symbol,
            name=coin.get("name") or symbol,
            market="crypto",
            market_type="crypto",
            quote_currency="USD",
            coingecko_id=cg_id,
        ))
    return out


def remote_search(query: str, limit: int = 20) -> list[dict]:
    """
    Merged remote candidate list (crypto + equities/FX/commodities), cached and
    failure-tolerant. Never raises — returns [] on any provider error.
    """
    query = (query or "").strip()
    if len(query) < 2:
        return []

    cache_key = f"asset_remote_search:{query.lower()}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    results: list[dict] = []
    try:
        results.extend(_coingecko_search(query, limit))
        results.extend(_twelvedata_search(query, limit))
    except Exception as exc:  # defensive: remote search must never break the picker
        logger.warning("remote_search unexpected error for %r: %s", query, exc)

    # De-dupe on (symbol, market_type); keep first (crypto listed first).
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for c in results:
        key = (c["symbol"], c["market_type"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    deduped = deduped[:limit]
    cache.set(cache_key, deduped, timeout=_REMOTE_TTL)
    return deduped
