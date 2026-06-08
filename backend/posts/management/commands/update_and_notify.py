"""
Management command: update_and_notify

Observer Design Pattern entry point — called periodically by a scheduler
(cron, Render cron, Celery Beat) to:
  1. Fetch fresh OHLC price data for ALL assets from external APIs
  2. Notify all subscribed Positions and HardClaims via AssetSubscription
  3. Recalculate profitability scores for users whose positions transitioned

Replaces the old resolve_positions and resolve_claims commands for resolution.

Usage:
    uv run python manage.py update_and_notify

Recommended cron schedule (every 10 minutes):
    */10 * * * * cd /path/to/backend && uv run python manage.py update_and_notify
"""

from django.core.management.base import BaseCommand
from posts.asset_updater import update_all_assets
from posts.profitability import recalculate_all_profitabilities


class Command(BaseCommand):
    help = (
        "Observer Pattern: fetch fresh prices for all assets, "
        "notify subscribed positions, and recalculate profitabilities."
    )

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Starting asset price update & notification cycle..."))

        # 1. Update all asset prices and notify subscribers
        results = update_all_assets()

        self.stdout.write(
            f"  Assets updated: {results['assets_updated']}, "
            f"failed: {results['assets_failed']}"
        )
        self.stdout.write(
            f"  Subscriptions notified: {results['total_notified']}, "
            f"transitioned: {results['total_transitioned']}, "
            f"errors: {results['total_errors']}"
        )

        # 2. Recalculate profitability scores
        if results["total_transitioned"] > 0:
            self.stdout.write(self.style.NOTICE("Recalculating profitabilities..."))
            recalculate_all_profitabilities()
            self.stdout.write(self.style.SUCCESS("Profitabilities updated."))

        self.stdout.write(self.style.SUCCESS("Update & notify cycle complete."))
