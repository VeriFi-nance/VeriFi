"""
Management command: seed_assets

Populate the Asset catalog so the search-always picker has a real universe to
draw on. Idempotent (update_or_create on symbol+market_type via
posts.asset_providers), guarded per-source so one provider failing never aborts
the others, and rate-limit aware for the TwelveData free tier.

Usage:
    uv run python manage.py seed_assets                      # all markets
    uv run python manage.py seed_assets --markets crypto     # subset
    uv run python manage.py seed_assets --markets crypto,bist --crypto-limit 100
    uv run python manage.py seed_assets --markets nasdaq --stocks-limit 500

Markets: crypto, nasdaq, bist, forex, commodity
"""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand

from posts.asset_providers import get_or_create_asset

ALL_MARKETS = ("crypto", "nasdaq", "bist", "forex", "commodity")

# Small curated fallback so verification (and a demo) still works when remote
# reference endpoints are unavailable or rate-limited.
_FALLBACK_NASDAQ = [
    ("AAPL", "Apple Inc."), ("MSFT", "Microsoft Corp."), ("GOOGL", "Alphabet Inc."),
    ("AMZN", "Amazon.com Inc."), ("NVDA", "NVIDIA Corp."), ("META", "Meta Platforms Inc."),
    ("TSLA", "Tesla Inc."), ("AMD", "Advanced Micro Devices"), ("NFLX", "Netflix Inc."),
    ("INTC", "Intel Corp."),
]
_FALLBACK_BIST = [
    ("THYAO", "Türk Hava Yolları"), ("AKBNK", "Akbank"), ("GARAN", "Garanti BBVA"),
    ("ASELS", "Aselsan"), ("KCHOL", "Koç Holding"), ("SISE", "Şişecam"),
    ("EREGL", "Ereğli Demir Çelik"), ("BIMAS", "BİM"), ("SAHOL", "Sabancı Holding"),
    ("TUPRS", "Tüpraş"),
]
_FALLBACK_FOREX = [
    ("EUR/USD", "Euro / US Dollar"), ("GBP/USD", "British Pound / US Dollar"),
    ("USD/TRY", "US Dollar / Turkish Lira"), ("USD/JPY", "US Dollar / Japanese Yen"),
]
_FALLBACK_COMMODITY = [
    ("XAU/USD", "Gold"), ("XAG/USD", "Silver"), ("WTI/USD", "Crude Oil WTI"),
]


def _http_get_json(url: str, timeout: int = 15):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "VeriFi/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class Command(BaseCommand):
    help = "Seed the Asset catalog (crypto / nasdaq / bist / forex / commodity)."

    def add_arguments(self, parser):
        parser.add_argument("--markets", default=",".join(ALL_MARKETS),
                            help="Comma list of markets to seed. Default: all.")
        parser.add_argument("--crypto-limit", type=int, default=250)
        parser.add_argument("--stocks-limit", type=int, default=300,
                            help="Max equities per stock exchange (nasdaq/bist).")

    def handle(self, *args, **opts):
        markets = [m.strip().lower() for m in opts["markets"].split(",") if m.strip()]
        unknown = [m for m in markets if m not in ALL_MARKETS]
        if unknown:
            self.stderr.write(self.style.ERROR(f"Unknown markets: {unknown}"))
            return

        total = 0
        if "crypto" in markets:
            total += self._seed_crypto(opts["crypto_limit"])
        if "nasdaq" in markets:
            total += self._seed_stock_exchange("nasdaq", "NASDAQ", opts["stocks_limit"], _FALLBACK_NASDAQ)
        if "bist" in markets:
            total += self._seed_stock_exchange("bist", "BIST", opts["stocks_limit"], _FALLBACK_BIST)
        if "forex" in markets:
            total += self._seed_pairs("forex", "forex_pairs", _FALLBACK_FOREX)
        if "commodity" in markets:
            total += self._seed_pairs("commodity", "commodities", _FALLBACK_COMMODITY)

        # Make the new tickers recognizable in free-text claim extraction.
        try:
            from posts.claim_extraction import refresh_whitelist
            refresh_whitelist(force=True)
        except Exception as exc:
            self.stderr.write(self.style.WARNING(f"Whitelist refresh failed: {exc}"))

        self.stdout.write(self.style.SUCCESS(f"Seeded/updated {total} assets across {markets}."))

    # -- crypto (CoinGecko markets, free, reliable) --------------------------
    def _seed_crypto(self, limit: int) -> int:
        count = 0
        per_page = 250
        pages = (limit + per_page - 1) // per_page
        for page in range(1, pages + 1):
            params = urlencode({
                "vs_currency": "usd", "order": "market_cap_desc",
                "per_page": min(per_page, limit - count), "page": page,
            })
            url = f"https://api.coingecko.com/api/v3/coins/markets?{params}"
            try:
                rows = _http_get_json(url)
            except (HTTPError, URLError, ValueError) as exc:
                self.stderr.write(self.style.WARNING(f"CoinGecko page {page} failed: {exc}"))
                break
            if not isinstance(rows, list) or not rows:
                break
            for coin in rows:
                symbol = (coin.get("symbol") or "").strip()
                if not symbol or len(symbol) > 10:  # Asset.symbol is varchar(10)
                    continue
                get_or_create_asset(
                    symbol=symbol, name=coin.get("name") or symbol,
                    market="crypto", quote_currency="USD",
                    coingecko_id=coin.get("id"),
                )
                count += 1
                if count >= limit:
                    break
            time.sleep(1.2)  # CoinGecko public rate limit
            if count >= limit:
                break
        self.stdout.write(f"  crypto: {count}")
        return count

    # -- equities (TwelveData /stocks, fallback to curated list) -------------
    def _seed_stock_exchange(self, market: str, exchange: str, limit: int, fallback) -> int:
        rows = []
        api_key = getattr(settings, "TWELVE_DATA_API_KEY", "")
        if api_key:
            params = urlencode({"exchange": exchange, "apikey": api_key})
            try:
                payload = _http_get_json(f"https://api.twelvedata.com/stocks?{params}")
                rows = payload.get("data", []) if isinstance(payload, dict) else []
            except (HTTPError, URLError, ValueError) as exc:
                self.stderr.write(self.style.WARNING(f"TwelveData /stocks {exchange} failed: {exc}"))
        count = 0
        if rows:
            for item in rows[:limit]:
                symbol = (item.get("symbol") or "").strip()
                if not symbol or len(symbol) > 10:  # Asset.symbol is varchar(10)
                    continue
                get_or_create_asset(symbol=symbol, name=item.get("name") or symbol, market=market)
                count += 1
        else:
            for symbol, name in fallback:
                get_or_create_asset(symbol=symbol, name=name, market=market)
                count += 1
            self.stdout.write(f"  {market}: used curated fallback")
        self.stdout.write(f"  {market}: {count}")
        return count

    # -- forex / commodity pairs --------------------------------------------
    def _seed_pairs(self, market: str, endpoint: str, fallback) -> int:
        rows = []
        api_key = getattr(settings, "TWELVE_DATA_API_KEY", "")
        if api_key:
            try:
                payload = _http_get_json(f"https://api.twelvedata.com/{endpoint}?apikey={api_key}")
                rows = payload.get("data", []) if isinstance(payload, dict) else []
            except (HTTPError, URLError, ValueError) as exc:
                self.stderr.write(self.style.WARNING(f"TwelveData /{endpoint} failed: {exc}"))
        count = 0
        if rows:
            for item in rows:
                symbol = (item.get("symbol") or "").strip()
                if not symbol or "/" not in symbol or len(symbol) > 10:
                    continue
                get_or_create_asset(symbol=symbol, name=item.get("name") or symbol, market=market)
                count += 1
        else:
            for symbol, name in fallback:
                get_or_create_asset(symbol=symbol, name=name, market=market)
                count += 1
            self.stdout.write(f"  {market}: used curated fallback")
        self.stdout.write(f"  {market}: {count}")
        return count
