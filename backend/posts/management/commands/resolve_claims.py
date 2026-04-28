from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from posts.models import HardClaim, Post
from posts.resolution import ResolutionError, preview_resolution, resolve_hard_claim


class Command(BaseCommand):
    help = "Resolve HardClaims by ID, by Post, or all due & undetermined claims."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--claim",
            type=int,
            help="Resolve a single HardClaim by its ID.",
        )
        group.add_argument(
            "--post",
            type=int,
            help="Resolve all undetermined HardClaims attached to a Post ID.",
        )
        group.add_argument(
            "--all",
            action="store_true",
            default=False,
            help="Resolve every undetermined HardClaim whose 'until' date has passed.",
        )
        parser.add_argument(
            "--preview",
            action="store_true",
            default=False,
            help="Dry-run: compute resolution but do NOT save to the database.",
        )

    def handle(self, *args, **options):
        preview = options["preview"]
        mode_label = "PREVIEW" if preview else "RESOLVE"

        if options["claim"]:
            claims = self._claims_by_id(options["claim"])
        elif options["post"]:
            claims = self._claims_by_post(options["post"])
        else:
            claims = self._all_due_claims()

        if not claims:
            self.stdout.write(self.style.WARNING("No matching undetermined claims found."))
            return

        self.stdout.write(f"[{mode_label}] Processing {len(claims)} claim(s)…\n")

        resolved = 0
        failed = 0
        for claim in claims:
            try:
                result = preview_resolution(claim) if preview else resolve_hard_claim(claim)
                status = result["status"]
                pct = result["computed_change_pct"]
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Claim {claim.id} ({claim.asset.symbol} {claim.direction} {claim.percentage}%) "
                        f"-> {status}  (change: {pct}%)"
                    )
                )
                resolved += 1
            except ResolutionError as exc:
                self.stdout.write(
                    self.style.ERROR(f"  Claim {claim.id}: {exc.code} — {exc.message}")
                )
                failed += 1

        self.stdout.write(f"\nDone. {resolved} resolved, {failed} failed.")

    # ------------------------------------------------------------------

    def _claims_by_id(self, claim_id: int) -> list[HardClaim]:
        try:
            claim = HardClaim.objects.select_related("asset").get(pk=claim_id)
        except HardClaim.DoesNotExist:
            raise CommandError(f"HardClaim {claim_id} does not exist.")
        if claim.status != HardClaim.Status.UNDETERMINED:
            raise CommandError(
                f"HardClaim {claim_id} is already '{claim.status}' — nothing to resolve."
            )
        return [claim]

    def _claims_by_post(self, post_id: int) -> list[HardClaim]:
        try:
            post = Post.objects.get(pk=post_id)
        except Post.DoesNotExist:
            raise CommandError(f"Post {post_id} does not exist.")
        return list(
            post.hard_claims.select_related("asset").filter(
                status=HardClaim.Status.UNDETERMINED
            )
        )

    def _all_due_claims(self) -> list[HardClaim]:
        today = datetime.now(timezone.utc).date()
        return list(
            HardClaim.objects.select_related("asset")
            .filter(status=HardClaim.Status.UNDETERMINED, until__lte=today)
            .order_by("id")
        )
