from django.db import migrations, models
from django.utils import timezone


def backfill(apps, schema_editor):
    WalletUser = apps.get_model("accounts", "WalletUser")
    now = timezone.now()
    WalletUser.objects.update(rep=200.0, energy=4.0, last_energy_grant=now)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_profitabilitycache"),
    ]

    operations = [
        migrations.AddField(
            model_name="walletuser",
            name="rep",
            field=models.FloatField(default=200.0),
        ),
        migrations.AddField(
            model_name="walletuser",
            name="energy",
            field=models.FloatField(default=4.0),
        ),
        migrations.AddField(
            model_name="walletuser",
            name="last_energy_grant",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
