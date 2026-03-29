from datetime import timedelta
from django.db import migrations, models


def fix_until_dates(apps, schema_editor):
    """Set until = created_at + 1 year for any row that violates the constraint."""
    HardClaim = apps.get_model("posts", "HardClaim")
    for claim in HardClaim.objects.all():
        created_date = claim.created_at.date()
        if claim.until <= created_date:
            claim.until = created_date + timedelta(days=365)
            claim.save(update_fields=["until"])


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0009_hardclaim_created_at"),
    ]

    operations = [
        # Fix existing rows first so the constraint doesn't fail on them
        migrations.RunPython(fix_until_dates, reverse_code=migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="hardclaim",
            constraint=models.CheckConstraint(
                condition=models.Q(until__gt=models.F("created_at")),
                name="hardclaim_until_after_created_at",
            ),
        ),
    ]
