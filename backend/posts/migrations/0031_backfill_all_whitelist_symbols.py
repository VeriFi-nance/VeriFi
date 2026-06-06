from django.db import migrations

def backfill_whitelist_symbols(apps, schema_editor):
    Asset = apps.get_model("posts", "Asset")

    # Mappings for Crypto
    crypto_mappings = {
        "SOL": {
            "provider": "coingecko",
            "provider_symbol": "solana",
            "binance_symbol": "SOLUSDT",
            "kucoin_symbol": "SOL-USDT",
            "kraken_pair": "SOLUSD",
            "twelvedata_symbol": "SOL/USD",
        },
        "BNB": {
            "provider": "coingecko",
            "provider_symbol": "binancecoin",
            "binance_symbol": "BNBUSDT",
            "kucoin_symbol": "BNB-USDT",
            "kraken_pair": "BNBUSD",
            "twelvedata_symbol": "BNB/USD",
        },
        "XRP": {
            "provider": "coingecko",
            "provider_symbol": "ripple",
            "binance_symbol": "XRPUSDT",
            "kucoin_symbol": "XRP-USDT",
            "kraken_pair": "XRPUSD",
            "twelvedata_symbol": "XRP/USD",
        },
        "ADA": {
            "provider": "coingecko",
            "provider_symbol": "cardano",
            "binance_symbol": "ADAUSDT",
            "kucoin_symbol": "ADA-USDT",
            "kraken_pair": "ADAUSD",
            "twelvedata_symbol": "ADA/USD",
        },
        "AVAX": {
            "provider": "coingecko",
            "provider_symbol": "avalanche-2",
            "binance_symbol": "AVAXUSDT",
            "kucoin_symbol": "AVAX-USDT",
            "kraken_pair": "AVAXUSD",
            "twelvedata_symbol": "AVAX/USD",
        },
        "DOGE": {
            "provider": "coingecko",
            "provider_symbol": "dogecoin",
            "binance_symbol": "DOGEUSDT",
            "kucoin_symbol": "DOGE-USDT",
            "kraken_pair": "XDGUSD",
            "twelvedata_symbol": "DOGE/USD",
        },
        "DOT": {
            "provider": "coingecko",
            "provider_symbol": "polkadot",
            "binance_symbol": "DOTUSDT",
            "kucoin_symbol": "DOT-USDT",
            "kraken_pair": "DOTUSD",
            "twelvedata_symbol": "DOT/USD",
        },
        "LINK": {
            "provider": "coingecko",
            "provider_symbol": "chainlink",
            "binance_symbol": "LINKUSDT",
            "kucoin_symbol": "LINK-USDT",
            "kraken_pair": "LINKUSD",
            "twelvedata_symbol": "LINK/USD",
        },
    }

    for symbol, values in crypto_mappings.items():
        Asset.objects.filter(symbol=symbol).update(**values)

    # Mappings for Traditional (Stocks/Forex)
    traditional_mappings = {
        # Stocks (equity)
        "AAPL": {"provider": "yfinance", "provider_symbol": "AAPL", "twelvedata_symbol": "AAPL"},
        "MSFT": {"provider": "yfinance", "provider_symbol": "MSFT", "twelvedata_symbol": "MSFT"},
        "GOOGL": {"provider": "yfinance", "provider_symbol": "GOOGL", "twelvedata_symbol": "GOOGL"},
        "AMZN": {"provider": "yfinance", "provider_symbol": "AMZN", "twelvedata_symbol": "AMZN"},
        "NVDA": {"provider": "yfinance", "provider_symbol": "NVDA", "twelvedata_symbol": "NVDA"},
        "TSLA": {"provider": "yfinance", "provider_symbol": "TSLA", "twelvedata_symbol": "TSLA"},
        "META": {"provider": "yfinance", "provider_symbol": "META", "twelvedata_symbol": "META"},
        "NFLX": {"provider": "yfinance", "provider_symbol": "NFLX", "twelvedata_symbol": "NFLX"},
        "AMD": {"provider": "yfinance", "provider_symbol": "AMD", "twelvedata_symbol": "AMD"},
        "INTC": {"provider": "yfinance", "provider_symbol": "INTC", "twelvedata_symbol": "INTC"},
        "COIN": {"provider": "yfinance", "provider_symbol": "COIN", "twelvedata_symbol": "COIN"},
        "PYPL": {"provider": "yfinance", "provider_symbol": "PYPL", "twelvedata_symbol": "PYPL"},
        "PLTR": {"provider": "yfinance", "provider_symbol": "PLTR", "twelvedata_symbol": "PLTR"},
        "UBER": {"provider": "yfinance", "provider_symbol": "UBER", "twelvedata_symbol": "UBER"},
        "DIS": {"provider": "yfinance", "provider_symbol": "DIS", "twelvedata_symbol": "DIS"},
        # Forex
        "EUR": {"provider": "yfinance", "provider_symbol": "EURUSD=X", "twelvedata_symbol": "EUR/USD"},
        "GBP": {"provider": "yfinance", "provider_symbol": "GBPUSD=X", "twelvedata_symbol": "GBP/USD"},
        "JPY": {"provider": "yfinance", "provider_symbol": "JPYUSD=X", "twelvedata_symbol": "JPY/USD"},
        "CHF": {"provider": "yfinance", "provider_symbol": "CHFUSD=X", "twelvedata_symbol": "CHF/USD"},
        "TRY": {"provider": "yfinance", "provider_symbol": "TRYUSD=X", "twelvedata_symbol": "TRY/USD"},
        "AUD": {"provider": "yfinance", "provider_symbol": "AUDUSD=X", "twelvedata_symbol": "AUD/USD"},
        "CAD": {"provider": "yfinance", "provider_symbol": "CADUSD=X", "twelvedata_symbol": "CAD/USD"},
        "NZD": {"provider": "yfinance", "provider_symbol": "NZDUSD=X", "twelvedata_symbol": "NZD/USD"},
        "CNY": {"provider": "yfinance", "provider_symbol": "CNYUSD=X", "twelvedata_symbol": "CNY/USD"},
    }

    for symbol, values in traditional_mappings.items():
        Asset.objects.filter(symbol=symbol).update(**values)

class Migration(migrations.Migration):
    dependencies = [
        ("posts", "0030_merge_20260601_1228"),
    ]

    operations = [
        migrations.RunPython(
            backfill_whitelist_symbols,
            reverse_code=migrations.RunPython.noop,
        )
    ]
