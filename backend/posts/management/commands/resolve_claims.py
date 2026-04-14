from datetime import date
from django.core.management.base import BaseCommand
from posts.models import HardClaim
from posts.resolution import resolve_hard_claim, ResolutionError

class Command(BaseCommand):
    help = "Automatically resolves HardClaims that have passed their deadline."

    def handle(self, *args, **options):
        due_claims = HardClaim.objects.filter(
            status=HardClaim.Status.UNDETERMINED,
            until__lte=date.today()
        )

        count = due_claims.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No due claims to resolve."))
            return

        self.stdout.write(f"Found {count} due claims to resolve.")

        success_count = 0
        error_count = 0

        for claim in due_claims:
            self.stdout.write(f"Resolving claim {claim.id} (Asset: {claim.asset.symbol})...")
            try:
                result = resolve_hard_claim(claim)
                self.stdout.write(
                    self.style.SUCCESS(f"  -> Successfully resolved claim {claim.id} as {result['status']}")
                )
                success_count += 1
            except ResolutionError as e:
                self.stderr.write(
                    self.style.ERROR(f"  -> ResolutionError for claim {claim.id}: {e.message}")
                )
                error_count += 1
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"  -> Unexpected error for claim {claim.id}: {str(e)}")
                )
                error_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished auto-resolution. Success: {success_count}, Errors: {error_count}"
            )
        )
