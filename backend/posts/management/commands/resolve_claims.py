from datetime import date

from django.core.management.base import BaseCommand

from posts.models import HardClaim
from posts.resolution import ResolutionError, resolve_hard_claim


def due_claims_queryset():
    """Undetermined claims whose deadline day has fully elapsed (UTC)."""
    return HardClaim.objects.filter(
        status=HardClaim.Status.UNDETERMINED,
        until__lt=date.today(),
    ).select_related("asset")


class Command(BaseCommand):
    help = "Automatically resolves HardClaims that have passed their deadline."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List due claims without resolving them.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        due_claims = due_claims_queryset()
        count = due_claims.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No due claims to resolve."))
            return

        if dry_run:
            self.stdout.write(f"Found {count} due claim(s) (dry run):")
            for claim in due_claims:
                self.stdout.write(
                    f"  id={claim.id} asset={claim.asset.symbol} until={claim.until} "
                    f"direction={claim.direction!r} value_type={claim.value_type}"
                )
            return

        self.stdout.write(f"Found {count} due claims to resolve.")

        success_count = 0
        error_count = 0

        for claim in due_claims:
            self.stdout.write(f"Resolving claim {claim.id} (Asset: {claim.asset.symbol})...")
            try:
                result = resolve_hard_claim(claim)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  -> Successfully resolved claim {claim.id} as {result['status']}"
                    )
                )
                success_count += 1
            except ResolutionError as e:
                self.stderr.write(
                    self.style.ERROR(
                        f"  -> ResolutionError for claim {claim.id} [{e.code}]: {e.message}"
                    )
                )
                error_count += 1
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"  -> Unexpected error for claim {claim.id}: {e}")
                )
                error_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished auto-resolution. Success: {success_count}, Errors: {error_count}"
            )
        )

        if error_count > 0:
            raise SystemExit(1)
