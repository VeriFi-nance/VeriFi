"""
Provider-symbol mapping for the Asset catalog.

Single source of truth for turning a (market, raw symbol) pair into the
per-provider symbol fields the oracle reads when it prices a claim
(`binance_symbol`, `kucoin_symbol`, `kraken_pair`, `twelvedata_symbol`,
`provider_symbol`, `quote_currency`).  Reused by the `seed_assets`
management command and the lazy `/assets/resolve/` endpoint so both produce
identical, priceable rows.

An asset with wrong/empty provider symbols fails *silently* at resolution
(ohlc_fetcher exhausts its fallback chain and raises), so the mapping here is
the make-or-break correctness boundary for the whole feature.

Markets accepted (the `market` argument):
    "crypto"     -> MarketType.CRYPTO
    "nasdaq"     -> MarketType.EQUITY   (US, USD)
    "bist"       -> MarketType.EQUITY   (Borsa Istanbul, TRY)
    "forex"      -> MarketType.FOREX
    "commodity"  -> MarketType.COMMODITY
"""

from __future__ import annotations

from typing import Optional, TypedDict

from .models import Asset

# Crypto bases whose Kraken pair code differs from the common ticker.
# Kraken still uses the legacy XBT code for Bitcoin.
_KRAKEN_BASE_OVERRIDES = {
    "BTC": "XBT",
}

# Markets we know how to map. Exposed for callers that want to validate input.
SUPPORTED_MARKETS = ("crypto", "nasdaq", "bist", "forex", "commodity")


class AssetFields(TypedDict, total=False):
    name: str
    symbol: str
    market_type: str
    provider: str
    provider_symbol: str
    quote_currency: str
    binance_symbol: str
    kucoin_symbol: str
    kraken_pair: str
    twelvedata_symbol: str


def _crypto_fields(symbol: str, *, quote: str, coingecko_id: Optional[str]) -> AssetFields:
    base = symbol.upper()
    kraken_base = _KRAKEN_BASE_OVERRIDES.get(base, base)
    return {
        "market_type": Asset.MarketType.CRYPTO,
        "provider": Asset.Provider.COINGECKO,
        "provider_symbol": (coingecko_id or base.lower()),
        "quote_currency": quote,
        "binance_symbol": f"{base}{quote}T" if quote == "USD" else f"{base}{quote}",
        "kucoin_symbol": f"{base}-{quote}T" if quote == "USD" else f"{base}-{quote}",
        "kraken_pair": f"{kraken_base}{quote}",
        # TwelveData crypto uses slash form; harmless extra fallback.
        "twelvedata_symbol": f"{base}/{quote}",
    }


def _equity_fields(symbol: str, *, market: str) -> AssetFields:
    base = symbol.upper()
    if market == "bist":
        return {
            "market_type": Asset.MarketType.EQUITY,
            "provider": Asset.Provider.TWELVEDATA,
            # Yahoo Finance uses the .IS suffix for Borsa Istanbul.
            "provider_symbol": f"{base}.IS",
            # SYMBOL:EXCHANGE form — _fetch_twelvedata_ohlc splits this into
            # the TwelveData `symbol` + `exchange` query params.
            "twelvedata_symbol": f"{base}:BIST",
            "quote_currency": "TRY",
        }
    # nasdaq / generic US equity
    return {
        "market_type": Asset.MarketType.EQUITY,
        "provider": Asset.Provider.TWELVEDATA,
        "provider_symbol": base,  # Yahoo Finance bare ticker
        "twelvedata_symbol": base,
        "quote_currency": "USD",
    }


def _pair_fields(symbol: str, *, market: str) -> AssetFields:
    """Forex / commodity: TwelveData slash pairs e.g. EUR/USD, XAU/USD."""
    sym = symbol.upper().replace("\\", "/")
    quote = sym.split("/")[1] if "/" in sym else "USD"
    market_type = (
        Asset.MarketType.FOREX if market == "forex" else Asset.MarketType.COMMODITY
    )
    return {
        "market_type": market_type,
        "provider": Asset.Provider.TWELVEDATA,
        "twelvedata_symbol": sym,
        "provider_symbol": sym,
        "quote_currency": quote,
    }


def build_asset_fields(
    *,
    symbol: str,
    name: str,
    market: str,
    quote_currency: str = "USD",
    coingecko_id: Optional[str] = None,
) -> AssetFields:
    """
    Build the full set of Asset field kwargs for a (market, symbol) pair.

    `symbol` is the display ticker (BTC, AAPL, AKBNK, EUR/USD).
    Raises ValueError for an unsupported market so callers fail loud at seed
    time rather than persisting an unpriceable row.
    """
    market = market.lower().strip()
    if market not in SUPPORTED_MARKETS:
        raise ValueError(f"Unsupported market: {market!r}")

    display_symbol = symbol.upper().strip()

    if market == "crypto":
        fields = _crypto_fields(display_symbol, quote=quote_currency.upper(), coingecko_id=coingecko_id)
    elif market in ("nasdaq", "bist"):
        fields = _equity_fields(display_symbol, market=market)
    else:  # forex / commodity
        fields = _pair_fields(display_symbol, market=market)

    fields["symbol"] = display_symbol
    # Asset.name is varchar(100); keep provider names from overflowing the column.
    fields["name"] = (name.strip() or display_symbol)[:100]
    return fields


def get_or_create_asset(
    *,
    symbol: str,
    name: str,
    market: str,
    quote_currency: str = "USD",
    coingecko_id: Optional[str] = None,
) -> tuple[Asset, bool]:
    """
    Idempotently persist an Asset for a (market, symbol) pair, keyed on
    (symbol, market_type). Returns (asset, created). Used by both the seed
    command and the lazy resolve endpoint.
    """
    fields = build_asset_fields(
        symbol=symbol,
        name=name,
        market=market,
        quote_currency=quote_currency,
        coingecko_id=coingecko_id,
    )
    lookup = {"symbol": fields["symbol"], "market_type": fields["market_type"]}
    defaults = {k: v for k, v in fields.items() if k not in lookup}
    return Asset.objects.update_or_create(**lookup, defaults=defaults)
