from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0032_merge_20260603_0242"),
    ]

    operations = [
        migrations.AddField(
            model_name="hardclaim",
            name="reference_price",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="hardclaim",
            name="reference_price_url",
            field=models.TextField(blank=True, default=""),
        ),
    ]
