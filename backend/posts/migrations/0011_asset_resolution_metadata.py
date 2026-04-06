from django.db import migrations, models


def populate_asset_resolution_metadata(apps, schema_editor):
    Asset = apps.get_model("posts", "Asset")

    mappings = {
        "BTC": {
            "market_type": "crypto",
            "provider": "coingecko",
            "provider_symbol": "bitcoin",
            "quote_currency": "USD",
        },
        "ETH": {
            "market_type": "crypto",
            "provider": "coingecko",
            "provider_symbol": "ethereum",
            "quote_currency": "USD",
        },
        "USD": {
            "market_type": "forex",
            "provider": "yfinance",
            "provider_symbol": "EURUSD=X",
            "quote_currency": "USD",
        },
        "COCOA": {
            "market_type": "commodity",
            "provider": "yfinance",
            "provider_symbol": "CC=F",
            "quote_currency": "USD",
        },
    }

    for symbol, values in mappings.items():
        Asset.objects.filter(symbol=symbol).update(**values)


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0010_hardclaim_until_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="market_type",
            field=models.CharField(
                choices=[
                    ("crypto", "crypto"),
                    ("forex", "forex"),
                    ("commodity", "commodity"),
                    ("equity", "equity"),
                    ("index", "index"),
                ],
                default="crypto",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="provider",
            field=models.CharField(
                choices=[("coingecko", "coingecko"), ("yfinance", "yfinance")],
                default="coingecko",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="provider_symbol",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="asset",
            name="quote_currency",
            field=models.CharField(default="USD", max_length=10),
        ),
        migrations.RunPython(
            populate_asset_resolution_metadata,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
