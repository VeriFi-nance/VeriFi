"""
Management command: seed_feed

Creates a handful of realistic demo WalletUsers, Assets, Posts with Claims,
and HardClaims so the feed looks populated during development.

Seed users carry real (deterministic, dev-only) secp256k1 keys, so every
seeded HardClaim gets a valid EIP-191 signature + claim_payload — the
"Download Proof" button and the /verify page work on seeded data. Each
claim also gets a reputation market (creator stake + trader buys) so the
MarketPanel renders instead of "No reputation market on this claim yet."

Usage:
    uv run python manage.py seed_feed
    uv run python manage.py seed_feed --clear   # wipe and re-seed
"""

import json
from datetime import date, datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from eth_account import Account
from eth_account.messages import encode_defunct

from accounts.models import WalletUser
from posts.models import Asset, HardClaim, Post
from posts.rep_market import MarketError, buy, init_market


ASSETS = [
    {"name": "Bitcoin", "symbol": "BTC", "description": "Peer-to-peer digital currency", "provider_symbol": "bitcoin", "quote_currency": "USD", "binance_symbol": "BTCUSDT"},
    {"name": "Ethereum", "symbol": "ETH", "description": "Smart contract platform", "provider_symbol": "ethereum", "quote_currency": "USD", "binance_symbol": "ETHUSDT"},
    {"name": "Solana", "symbol": "SOL", "description": "High-throughput L1 blockchain", "provider_symbol": "solana", "quote_currency": "USD", "binance_symbol": "SOLUSDT"},
]

# Dev-only deterministic private keys (never reuse outside local/demo data).
SEED_PRIVATE_KEYS = [
    "0x" + "11" * 32,
    "0x" + "22" * 32,
    "0x" + "33" * 32,
    "0x" + "44" * 32,
    "0x" + "55" * 32,
]

SEED_DATA = [
    {
        "user": 0,
        "content": (
            "Bitcoin will reach $150,000 by the end of Q2 2026. "
            "The halving effect combined with institutional adoption will drive this rally. "
            "I'm putting my reputation on the line for this prediction."
        ),
        "hard_claims": [
            {
                "asset": "BTC",
                "direction": "Bullish",
                "percentage": 78.9,
                "until": date.today() + timedelta(days=93),
                "status": "undetermined",
                "creator_stake": 40.0,
                "trader_buys": [(1, "YES"), (2, "NO"), (3, "YES")],
            }
        ],
    },
    {
        "user": 1,
        "content": (
            "Ethereum's Pectra upgrade will push ETH above $5k this quarter. "
            "EIP-4844 blob fee reductions are making L2s significantly cheaper, "
            "bringing a wave of new users on-chain."
        ),
        "hard_claims": [
            {
                "asset": "ETH",
                "direction": "Bullish",
                "percentage": 62.0,
                "until": date.today() + timedelta(days=91),
                "status": "undetermined",
                "creator_stake": 25.0,
                "trader_buys": [(0, "NO"), (4, "YES")],
            }
        ],
    },
    {
        "user": 2,
        "content": (
            "SOL is overvalued at current levels. "
            "Network instability and increasing competition from cheaper L2s "
            "will drag the price back to $80 within 60 days."
        ),
        "hard_claims": [
            {
                "asset": "SOL",
                "direction": "Bearish",
                "percentage": 43.5,
                "until": date.today() + timedelta(days=55),
                "status": "undetermined",
                "creator_stake": 15.0,
                "trader_buys": [(3, "NO"), (4, "NO"), (0, "YES")],
            }
        ],
    },
    {
        "user": 0,
        "content": (
            "My BTC call from last month was confirmed ✓. "
            "Halving supply shock is playing out exactly as modelled. "
            "Next target: $200k by year-end."
        ),
        "hard_claims": [
            {
                "asset": "BTC",
                "direction": "Bullish",
                "percentage": 55.0,
                "until": date.today() + timedelta(days=276),
                "status": "confirmed",
                "creator_stake": 60.0,
                "trader_buys": [(1, "YES"), (2, "YES"), (4, "NO")],
            }
        ],
    },
]


def _canonical_json(payload: dict) -> str:
    """Match posts.signature_verification._canonical_json exactly."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sign_claim_payload(private_key: str, payload: dict) -> str:
    signed = Account.sign_message(
        encode_defunct(text=_canonical_json(payload)), private_key=private_key
    )
    sig = signed.signature.hex()
    # ethers' verifyMessage on the /verify page requires the 0x prefix
    return sig if sig.startswith("0x") else f"0x{sig}"


class Command(BaseCommand):
    help = "Seed the database with demo posts, claims, hard claims, and markets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing seed data before re-seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            Post.objects.all().delete()
            HardClaim.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing posts and hard claims."))

        # Create / fetch assets
        asset_map: dict[str, Asset] = {}
        for a in ASSETS:
            obj, created = Asset.objects.get_or_create(symbol=a["symbol"], defaults=a)
            asset_map[a["symbol"]] = obj
            if created:
                self.stdout.write(f"  Created asset: {obj}")

        # Create / fetch users from deterministic dev keys
        accounts = [Account.from_key(pk) for pk in SEED_PRIVATE_KEYS]
        user_objs: list[WalletUser] = []
        for acct in accounts:
            u, _ = WalletUser.objects.get_or_create(address=acct.address.lower())
            # Re-seeding leaves rep spent on deleted markets; top back up so
            # market creation/buys don't fail with insufficient_rep.
            if u.rep < 200.0:
                u.rep = 200.0
                u.save(update_fields=["rep"])
            user_objs.append(u)

        # Create posts + hard claims (signed) + markets
        for entry in SEED_DATA:
            author = user_objs[entry["user"]]
            author_key = SEED_PRIVATE_KEYS[entry["user"]]
            post = Post.objects.create(author=author, content=entry["content"])
            self.stdout.write(f"  Post #{post.pk} by {author.address[:10]}…")

            for hc in entry.get("hard_claims", []):
                asset = asset_map[hc["asset"]]
                # Integral floats stored as ints so JS JSON.stringify on the
                # /verify page reproduces the exact signed canonical JSON.
                pct = float(hc["percentage"])
                payload = {
                    "asset_symbol": asset.symbol,
                    "author_username": author.username,
                    "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "direction": hc["direction"],
                    "percentage": int(pct) if pct.is_integer() else pct,
                    "until": hc["until"].isoformat(),
                }
                claim = HardClaim.objects.create(
                    author=author,
                    post=post,
                    asset=asset,
                    direction=hc["direction"],
                    percentage=hc["percentage"],
                    until=hc["until"],
                    status=hc["status"],
                    value_type=hc.get("value_type", "PERCENTAGE_UP"),
                    signature=_sign_claim_payload(author_key, payload),
                    claim_payload=payload,
                )

                if hasattr(claim, "market"):
                    continue
                try:
                    market = init_market(
                        claim,
                        author,
                        side="YES" if hc["direction"] == "Bullish" else "NO",
                        stake_rep=hc.get("creator_stake", 20.0),
                    )
                except MarketError as exc:
                    self.stdout.write(self.style.WARNING(
                        f"    Skipped market for claim #{claim.pk}: {exc}"
                    ))
                    continue
                for trader_idx, side in hc.get("trader_buys", []):
                    trader = user_objs[trader_idx]
                    if trader.pk == author.pk:
                        continue
                    try:
                        buy(market, trader, side)
                    except MarketError as exc:
                        self.stdout.write(self.style.WARNING(
                            f"    Skipped buy ({trader.address[:10]}… {side}): {exc}"
                        ))
                self.stdout.write(f"    Claim #{claim.pk}: signed ✓, market ✓")

        self.stdout.write(self.style.SUCCESS("Feed seeded successfully."))
