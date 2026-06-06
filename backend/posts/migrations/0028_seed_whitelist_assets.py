from django.db import migrations


# Mirrors the extraction whitelist in posts/claim_extraction.py so every asset a
# claim can reference is selectable in the frontend dropdowns.
WHITELIST_ASSETS = [
    # Fiat currencies (forex)
    ("USD", "US Dollar", "forex"),
    ("TRY", "Turkish Lira", "forex"),
    # Crypto
    ("BTC", "Bitcoin", "crypto"),
    ("ETH", "Ethereum", "crypto"),
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
        ("posts", "0027_backfill_crypto_ohlc_symbols"),
    ]

    operations = [
        migrations.RunPython(seed_whitelist_assets, reverse_code=migrations.RunPython.noop),
    ]
