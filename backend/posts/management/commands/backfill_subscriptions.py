"""
One-time management command to create AssetSubscription rows
for existing PENDING and ACTIVE positions that were created
before the Observer pattern was introduced.

Usage: python manage.py backfill_subscriptions

This command is idempotent — running it multiple times will not
create duplicate subscriptions.
"""

from django.core.management.base import BaseCommand
from posts.models import Position, AssetSubscription


class Command(BaseCommand):
    help = "Backfill AssetSubscription rows for existing active positions (Observer pattern)"

    def handle(self, *args, **kwargs):
        active_statuses = [Position.Status.PENDING, Position.Status.ACTIVE]
        positions = Position.objects.filter(status__in=active_statuses)

        created_count = 0
        skipped_count = 0

        for pos in positions:
            # Check if subscription already exists (idempotent)
            if AssetSubscription.objects.filter(position=pos).exists():
                skipped_count += 1
                continue

            AssetSubscription.objects.create(asset=pos.asset, position=pos)
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill complete. Created: {created_count}, Skipped (already exists): {skipped_count}"
            )
        )
