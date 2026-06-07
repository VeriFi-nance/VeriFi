from datetime import date

from django.core.management.base import BaseCommand

from posts.models import HardClaim
from posts.resolution import ResolutionError, reassess_hard_claim


def claims_to_reassess_queryset():
    """Past-deadline claims already marked confirmed/rejected with a stored entry price."""
    return HardClaim.objects.filter(
        status__in=(HardClaim.Status.CONFIRMED, HardClaim.Status.REJECTED),
        until__lt=date.today(),
        reference_price__isnull=False,
    ).select_related("asset")


class Command(BaseCommand):
    help = (
        "Re-run resolution for settled claims after reference_price changes. "
        "Replaces resolution events and updates status when the outcome changes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--claim-id", type=int, help="Only reassess a single claim id")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview new statuses without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        qs = claims_to_reassess_queryset()
        if options.get("claim_id"):
            qs = qs.filter(id=options["claim_id"])

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No settled claims to reassess."))
            return

        self.stdout.write(f"Found {count} settled claim(s) to reassess.")

        changed = 0
        unchanged = 0
        errors = 0

        for claim in qs.order_by("id"):
            label = (
                f"claim {claim.id} ({claim.asset.symbol}, until={claim.until}, "
                f"status={claim.status}, ref={claim.reference_price})"
            )
            try:
                if dry_run:
                    from posts.resolution import preview_resolution

                    result = preview_resolution(claim, allow_resolved=True)
                    new_status = result["status"]
                    if new_status == claim.status:
                        unchanged += 1
                        self.stdout.write(f"  {label} -> unchanged ({new_status})")
                    else:
                        changed += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"  {label} -> {claim.status} => {new_status}"
                            )
                        )
                    continue

                result = reassess_hard_claim(claim)
                if result["status_changed"]:
                    changed += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {label} -> {result['previous_status']} => {result['status']}"
                        )
                    )
                else:
                    unchanged += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  {label} -> unchanged ({result['status']})")
                    )
            except ResolutionError as exc:
                errors += 1
                self.stderr.write(
                    self.style.ERROR(f"  {label} -> ResolutionError [{exc.code}]: {exc.message}")
                )
            except Exception as exc:
                errors += 1
                self.stderr.write(self.style.ERROR(f"  {label} -> {exc}"))

        summary = f"Done. changed={changed} unchanged={unchanged} errors={errors}"
        if dry_run:
            summary = f"Dry run. would_change={changed} unchanged={unchanged} errors={errors}"
        self.stdout.write(self.style.SUCCESS(summary))

        if errors > 0:
            raise SystemExit(1)
