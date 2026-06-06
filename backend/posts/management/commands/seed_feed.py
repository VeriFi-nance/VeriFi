"""
Management command: seed_feed

Creates a handful of realistic demo WalletUsers, Assets, Posts with Claims,
and HardClaims so the feed looks populated during development.

Usage:
    uv run python manage.py seed_feed
    uv run python manage.py seed_feed --clear   # wipe and re-seed
"""

from datetime import date, timedelta
from django.core.management.base import BaseCommand
from accounts.models import WalletUser
from posts.models import Asset, HardClaim, Post


ASSETS = [
    {"name": "Bitcoin", "symbol": "BTC", "description": "Peer-to-peer digital currency"},
    {"name": "Ethereum", "symbol": "ETH", "description": "Smart contract platform"},
    {"name": "Solana", "symbol": "SOL", "description": "High-throughput blockchain"},
]

USERS = [
    "0x742d35cc6634c0532925a3b844bc454e4438f44e",
    "0xa91b3d4e8f0c12349c8c2a5b4d6f8901a3c7e2d1",
    "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
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
                "text": "BTC price will exceed $150,000 by 30 June 2026",
                "asset": "BTC",
                "direction": "Bullish",
                "percentage": 78.9,
                "until": date.today() + timedelta(days=93),
                "status": "undetermined",
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
                "text": "ETH closes above $5,000 before 1 July 2026",
                "asset": "ETH",
                "direction": "Bullish",
                "percentage": 62.0,
                "until": date.today() + timedelta(days=91),
                "status": "undetermined",
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
                "text": "SOL drops below $80 by end of May 2026",
                "asset": "SOL",
                "direction": "Bearish",
                "percentage": 43.5,
                "until": date.today() + timedelta(days=55),
                "status": "undetermined",
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
                "text": "BTC closes at or above $200,000 on 31 Dec 2026",
                "asset": "BTC",
                "direction": "Bullish",
                "percentage": 55.0,
                "until": date.today() + timedelta(days=276),
                "status": "confirmed",
            }
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the database with demo posts, claims, and hard claims."

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

        # Create / fetch users
        user_objs: list[WalletUser] = []
        for addr in USERS:
            u, _ = WalletUser.objects.get_or_create(address=addr)
            user_objs.append(u)

        # Create posts + claims + hard claims
        for entry in SEED_DATA:
            author = user_objs[entry["user"]]
            post = Post.objects.create(author=author, content=entry["content"])
            self.stdout.write(f"  Post #{post.pk} by {author.address[:10]}…")



            for hc in entry.get("hard_claims", []):
                HardClaim.objects.create(
                    author=author,
                    post=post,
                    asset=asset_map[hc["asset"]],
                    direction=hc["direction"],
                    percentage=hc["percentage"],
                    until=hc["until"],
                    status=hc["status"],
                    value_type=hc.get("value_type", "PERCENTAGE_UP"),
                    payda=hc.get("payda", ""),
                )

        self.stdout.write(self.style.SUCCESS("Feed seeded successfully."))
