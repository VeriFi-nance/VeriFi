from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0026_seed_whitelist_assets"),
    ]

    operations = [
        migrations.AddField(
            model_name="hardclaim",
            name="value_type",
            field=models.CharField(default="PERCENTAGE_UP", max_length=20),
        ),
        migrations.AddField(
            model_name="hardclaim",
            name="payda",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
    ]
