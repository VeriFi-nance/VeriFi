"""
Fix legacy HardClaim rows with inconsistent value_type / direction / magnitude.

Examples:
  - direction=Bearish but value_type=PERCENTAGE_UP
  - value_type=PRICE but direction=bullish while target is below spot (fall-to price)
  - percentage=50000 stored as PERCENTAGE_UP instead of PRICE
"""

from django.core.management.base import BaseCommand

from posts.models import HardClaim
from posts.resolution import reconcile_claim_fields


class Command(BaseCommand):
    help = "Backfill HardClaim direction and value_type for price vs percentage consistency"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print changes without writing to the database",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        updated = 0

        for claim in HardClaim.objects.select_related("asset").order_by("id"):
            old_direction = claim.direction
            old_value_type = claim.value_type
            new_direction, new_value_type = reconcile_claim_fields(claim)

            if (
                old_direction.lower() != new_direction
                or old_value_type.upper() != new_value_type
            ):
                self.stdout.write(
                    f"claim {claim.id}: "
                    f"{old_direction}/{old_value_type}/{claim.percentage} -> "
                    f"{new_direction}/{new_value_type}/{claim.percentage}"
                )
                if not dry_run:
                    HardClaim.objects.filter(id=claim.id).update(
                        direction=new_direction,
                        value_type=new_value_type,
                    )
                updated += 1

        suffix = " (dry run)" if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} claim(s){suffix}"))
