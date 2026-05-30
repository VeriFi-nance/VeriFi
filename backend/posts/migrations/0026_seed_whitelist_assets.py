from django.db import migrations


# Mirrors the extraction whitelist in posts/claim_extraction.py so every asset a
# claim can reference is selectable in the frontend dropdowns.
WHITELIST_ASSETS = [
    # Fiat currencies (forex)
    ("USD", "US Dollar", "forex"),
    ("EUR", "Euro", "forex"),
    ("GBP", "British Pound", "forex"),
    ("JPY", "Japanese Yen", "forex"),
    ("CHF", "Swiss Franc", "forex"),
    ("TRY", "Turkish Lira", "forex"),
    ("AUD", "Australian Dollar", "forex"),
    ("CAD", "Canadian Dollar", "forex"),
    ("NZD", "New Zealand Dollar", "forex"),
    ("CNY", "Chinese Yuan", "forex"),
    # Crypto
    ("BTC", "Bitcoin", "crypto"),
    ("ETH", "Ethereum", "crypto"),
    ("SOL", "Solana", "crypto"),
    ("BNB", "Binance Coin", "crypto"),
    ("XRP", "XRP", "crypto"),
    ("ADA", "Cardano", "crypto"),
    ("AVAX", "Avalanche", "crypto"),
    ("DOGE", "Dogecoin", "crypto"),
    ("DOT", "Polkadot", "crypto"),
    ("LINK", "Chainlink", "crypto"),
    # Stocks (equity)
    ("AAPL", "Apple", "equity"),
    ("MSFT", "Microsoft", "equity"),
    ("GOOGL", "Alphabet", "equity"),
    ("AMZN", "Amazon", "equity"),
    ("NVDA", "NVIDIA", "equity"),
    ("TSLA", "Tesla", "equity"),
    ("META", "Meta Platforms", "equity"),
    ("NFLX", "Netflix", "equity"),
    ("AMD", "AMD", "equity"),
    ("INTC", "Intel", "equity"),
    ("COIN", "Coinbase", "equity"),
    ("PYPL", "PayPal", "equity"),
    ("PLTR", "Palantir", "equity"),
    ("UBER", "Uber", "equity"),
    ("DIS", "Walt Disney", "equity"),
]


def seed_whitelist_assets(apps, schema_editor):
    Asset = apps.get_model("posts", "Asset")
    for symbol, name, market_type in WHITELIST_ASSETS:
        Asset.objects.get_or_create(
            symbol=symbol,
            defaults={"name": name, "market_type": market_type},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0025_claimmarket_claimstake"),
    ]

    operations = [
        migrations.RunPython(seed_whitelist_assets, reverse_code=migrations.RunPython.noop),
    ]
