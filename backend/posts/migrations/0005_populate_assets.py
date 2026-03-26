from django.db import migrations

def create_initial_assets(apps, schema_editor):
    Asset = apps.get_model('posts', 'Asset')
    initial_assets = [
        {'symbol': 'BTC', 'name': 'bitcoin'},
        {'symbol': 'USD', 'name': 'dollar'},
        {'symbol': 'ETH', 'name': 'ethereum'},
        {'symbol': 'COCOA', 'name': 'cocoa beans'},
    ]
    for asset_data in initial_assets:
        Asset.objects.get_or_create(
            symbol=asset_data['symbol'],
            defaults={'name': asset_data['name']}
        )

class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0004_hardclaim_author'),
    ]

    operations = [
        migrations.RunPython(create_initial_assets, reverse_code=migrations.RunPython.noop),
    ]
