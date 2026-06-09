from django.core.management.base import BaseCommand
from posts.models import HardClaim, AssetSubscription

class Command(BaseCommand):
    help = "Backfill AssetSubscriptions for all UNDETERMINED HardClaims"

    def handle(self, *args, **options):
        claims = HardClaim.objects.filter(status=HardClaim.Status.UNDETERMINED)
        count = claims.count()
        self.stdout.write(f"Found {count} undetermined HardClaims.")

        created_count = 0
        for claim in claims:
            # get_or_create to make it idempotent
            _, created = AssetSubscription.objects.get_or_create(
                hard_claim=claim,
                defaults={'asset': claim.asset}
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully created {created_count} subscriptions for HardClaims."))
