"""
Management command: backfill_demo_claims

Repairs artificially-populated demo data so it behaves like UI-created data:

1. **Signatures** — unsigned HardClaims can't show "Download Proof" or pass
   /verify. Their authors are synthetic personas without real keys, so each
   synthetic author gets a deterministic dev key (keccak of username), the
   user's address is rewritten to match, and every one of their unsigned
   claims gets a valid EIP-191 signature + canonical claim_payload.
   Users with at least one signed claim are treated as real and never touched.

2. **Markets** — claims without a ClaimMarket show "No reputation market on
   this claim yet." Each gets a market (author as creator) plus a few trader
   buys from other synthetic users; markets on already-resolved claims
   (confirmed/rejected) are resolved to the matching side.

Usage:
    uv run python manage.py backfill_demo_claims            # dry run
    uv run python manage.py backfill_demo_claims --apply
"""

import json
import random

from django.core.management.base import BaseCommand
from django.db.models import Q
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak

from accounts.models import WalletUser
from posts.models import HardClaim
from posts.rep_market import MarketError, buy, init_market, resolve

KEY_NAMESPACE = b"verifi-demo-key:"


def _derive_key(username: str) -> str:
    return "0x" + keccak(KEY_NAMESPACE + username.encode()).hex()


def _canonical_json(payload: dict) -> str:
    """Match posts.signature_verification._canonical_json exactly."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _js_number(value: float):
    """JSON.stringify(55.0) is "55" in JS but json.dumps gives "55.0" —
    store integral floats as ints so the /verify page's canonical JSON
    (built with JSON.stringify) matches what was signed."""
    f = float(value)
    return int(f) if f.is_integer() else f


def _build_payload(claim: HardClaim) -> dict:
    return {
        "asset_symbol": claim.asset.symbol,
        "author_username": claim.author.username,
        "created_at": claim.created_at.isoformat().replace("+00:00", "Z"),
        "direction": claim.direction,
        "percentage": _js_number(claim.percentage),
        "until": claim.until.isoformat(),
    }


class Command(BaseCommand):
    help = "Backfill signatures and reputation markets on artificially populated claims."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write changes (default is dry run).")

    def handle(self, *args, **options):
        apply = options["apply"]
        rng = random.Random(42)
        unsigned = HardClaim.objects.filter(Q(signature="") | Q(signature__isnull=True)).select_related("author", "asset")

        # Synthetic = authors of unsigned claims, plus users already rekeyed
        # by a previous run (address matches their derived dev key, which
        # makes re-runs idempotent). Anyone else is a real account and must
        # keep their address.
        real_author_ids = set(
            HardClaim.objects.exclude(signature="").exclude(signature__isnull=True).values_list("author_id", flat=True)
        )
        candidates = WalletUser.objects.filter(hard_claims__isnull=False).distinct()
        synth_ids = set(
            WalletUser.objects.filter(hard_claims__in=unsigned)
            .exclude(pk__in=real_author_ids)
            .values_list("pk", flat=True)
        )
        for u in candidates:
            if u.pk not in synth_ids and u.address == Account.from_key(_derive_key(u.username)).address.lower():
                synth_ids.add(u.pk)
        synth_users = WalletUser.objects.filter(pk__in=synth_ids)

        self.stdout.write(f"{'APPLY' if apply else 'DRY RUN'}: {unsigned.count()} unsigned claims, "
                          f"{synth_users.count()} synthetic authors")

        # 1. Rekey synthetic users
        keys: dict[int, str] = {}
        for u in synth_users:
            priv = _derive_key(u.username)
            derived = Account.from_key(priv).address.lower()
            keys[u.pk] = priv
            if u.address != derived:
                self.stdout.write(f"  rekey {u.username}: {u.address[:10]}… -> {derived[:10]}…")
                if apply:
                    u.address = derived
                    u.save(update_fields=["address"])

        # 2. (Re-)sign every synthetic-authored claim. Re-signing already
        # signed ones is idempotent and repairs payloads from older runs.
        signed = skipped = 0
        for claim in HardClaim.objects.filter(author_id__in=keys).select_related("author", "asset"):
            payload = _build_payload(claim)
            if apply:
                sig = Account.sign_message(
                    encode_defunct(text=_canonical_json(payload)),
                    private_key=keys[claim.author_id],
                ).signature.hex()
                # ethers' verifyMessage on the /verify page requires the 0x prefix
                claim.signature = sig if sig.startswith("0x") else f"0x{sig}"
                claim.claim_payload = payload
                claim.save(update_fields=["signature", "claim_payload"])
            signed += 1
        skipped = unsigned.exclude(author_id__in=keys).count()
        self.stdout.write(f"  signed {signed} claims" + (f", skipped {skipped} (real author, no key)" if skipped else ""))

        # 3. Create + (maybe) resolve markets
        no_market = HardClaim.objects.filter(market__isnull=True).select_related("author")
        synth_pool = list(synth_users)
        created = resolved = failed = 0
        for claim in no_market:
            if claim.author is None:
                continue
            side = "YES" if claim.direction.lower() == "bullish" else "NO"
            stake = float(rng.choice([10, 15, 20, 25, 40, 60]))
            stake = min(stake, max(10.0, claim.author.rep - 2.0))
            if not apply:
                created += 1
                continue
            try:
                market = init_market(claim, claim.author, side=side, stake_rep=stake)
            except MarketError as exc:
                self.stdout.write(self.style.WARNING(f"  claim {claim.pk}: market failed ({exc})"))
                failed += 1
                continue
            created += 1
            traders = rng.sample([u for u in synth_pool if u.pk != claim.author_id], k=min(rng.randint(3, 6), len(synth_pool) - 1))
            for t in traders:
                try:
                    buy(market, t, rng.choice(["YES", "NO"]))
                except MarketError:
                    pass
            if claim.status in ("confirmed", "rejected"):
                try:
                    resolve(market, "YES" if claim.status == "confirmed" else "NO")
                    resolved += 1
                except MarketError as exc:
                    self.stdout.write(self.style.WARNING(f"  claim {claim.pk}: resolve failed ({exc})"))
        self.stdout.write(f"  markets: {created} created, {resolved} resolved, {failed} failed")
        if not apply:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --apply to write."))
        else:
            self.stdout.write(self.style.SUCCESS("Backfill complete."))
