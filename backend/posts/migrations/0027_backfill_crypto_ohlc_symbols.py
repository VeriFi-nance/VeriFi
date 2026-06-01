from django.db import migrations


def backfill_crypto_ohlc_symbols(apps, schema_editor):
    Asset = apps.get_model("posts", "Asset")

    mappings = {
        "BTC": {
            "binance_symbol": "BTCUSDT",
            "kucoin_symbol": "BTC-USDT",
            "kraken_pair": "XBTUSD",
            "twelvedata_symbol": "BTC/USD",
        },
        "ETH": {
            "binance_symbol": "ETHUSDT",
            "kucoin_symbol": "ETH-USDT",
            "kraken_pair": "ETHUSD",
            "twelvedata_symbol": "ETH/USD",
        },
    }

    for symbol, values in mappings.items():
        Asset.objects.filter(symbol=symbol).update(**values)


class Migration(migrations.Migration):
    dependencies = [
        ("posts", "0026_add_feed_indexes"),
    ]

    operations = [
        migrations.RunPython(
            backfill_crypto_ohlc_symbols,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
