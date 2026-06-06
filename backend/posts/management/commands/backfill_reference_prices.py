"""Backfill reference_price on legacy hard claims."""

from django.core.management.base import BaseCommand

from posts.models import HardClaim
from posts.resolution import ResolutionError, capture_reference_price


class Command(BaseCommand):
    help = "Fetch and store entry prices for claims missing reference_price."

    def add_arguments(self, parser):
        parser.add_argument("--claim-id", type=int, help="Only backfill a single claim id")
        parser.add_argument("--dry-run", action="store_true", help="List claims without fetching")

    def handle(self, *args, **options):
        qs = HardClaim.objects.filter(reference_price__isnull=True).select_related("asset")
        if options.get("claim_id"):
            qs = qs.filter(id=options["claim_id"])

        total = qs.count()
        if options["dry_run"]:
            self.stdout.write(f"Would backfill {total} claim(s)")
            for claim in qs[:20]:
                self.stdout.write(f"  id={claim.id} created_at={claim.created_at.isoformat()}")
            return

        ok = 0
        failed = 0
        for claim in qs.iterator():
            try:
                capture_reference_price(claim)
                ok += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"claim {claim.id}: reference_price={claim.reference_price}"
                    )
                )
            except ResolutionError as exc:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(f"claim {claim.id}: {exc.code} — {exc.message}")
                )

        self.stdout.write(f"Done. ok={ok} failed={failed} total={total}")
