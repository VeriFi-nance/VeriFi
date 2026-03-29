from django.db import migrations


HARD_CLAIMS = [
    {
        "asset_symbol": "BTC",
        "text": "Bitcoin will double in price by the end of 2025.",
        "direction": "Bullish",
        "percentage": 100.0,
        "until": "2025-12-31",
        "status": "confirmed",
    },
    {
        "asset_symbol": "BTC",
        "text": "Bitcoin will surge 60% following the next halving cycle.",
        "direction": "Bullish",
        "percentage": 60.0,
        "until": "2025-09-30",
        "status": "rejected",
    },
    {
        "asset_symbol": "ETH",
        "text": "Ethereum will outperform Bitcoin with a 80% gain this year.",
        "direction": "Bullish",
        "percentage": 80.0,
        "until": "2025-12-31",
        "status": "confirmed",
    },
    {
        "asset_symbol": "ETH",
        "text": "Ethereum will drop 40% as layer-2 adoption cannibalizes demand.",
        "direction": "Bearish",
        "percentage": 40.0,
        "until": "2025-06-30",
        "status": "rejected",
    },
    {
        "asset_symbol": "BTC",
        "text": "Bitcoin will correct 30% before making new all-time highs.",
        "direction": "Bearish",
        "percentage": 30.0,
        "until": "2025-08-31",
        "status": "confirmed",
    },
    {
        "asset_symbol": "BTC",
        "text": "Bitcoin will reach $200k — a 150% gain — by Q4 2025.",
        "direction": "Bullish",
        "percentage": 150.0,
        "until": "2025-12-31",
        "status": "undetermined",
    },
    {
        "asset_symbol": "ETH",
        "text": "Ethereum will flip Bitcoin in market cap with a 120% rally.",
        "direction": "Bullish",
        "percentage": 120.0,
        "until": "2025-12-31",
        "status": "undetermined",
    },
    {
        "asset_symbol": "USD",
        "text": "The US Dollar index will fall 15% as inflation fears return.",
        "direction": "Bearish",
        "percentage": 15.0,
        "until": "2025-12-31",
        "status": "rejected",
    },
    {
        "asset_symbol": "COCOA",
        "text": "Cocoa will drop 50% from record highs as supply normalises.",
        "direction": "Bearish",
        "percentage": 50.0,
        "until": "2025-10-31",
        "status": "confirmed",
    },
    {
        "asset_symbol": "BTC",
        "text": "Bitcoin will end the year up at least 75% from January open.",
        "direction": "Bullish",
        "percentage": 75.0,
        "until": "2025-12-31",
        "status": "undetermined",
    },
]


def populate_hard_claims(apps, schema_editor):
    Asset = apps.get_model("posts", "Asset")
    HardClaim = apps.get_model("posts", "HardClaim")

    for claim_data in HARD_CLAIMS:
        try:
            asset = Asset.objects.get(symbol=claim_data["asset_symbol"])
        except Asset.DoesNotExist:
            continue
        HardClaim.objects.create(
            author=None,
            text=claim_data["text"],
            asset=asset,
            direction=claim_data["direction"],
            percentage=claim_data["percentage"],
            until=claim_data["until"],
            status=claim_data["status"],
        )


def depopulate_hard_claims(apps, schema_editor):
    HardClaim = apps.get_model("posts", "HardClaim")
    HardClaim.objects.filter(author=None).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0006_hardclaim_percentage"),
    ]

    operations = [
        migrations.RunPython(populate_hard_claims, reverse_code=depopulate_hard_claims),
    ]
