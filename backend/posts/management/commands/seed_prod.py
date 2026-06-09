"""
Management command: seed_prod

Fill the database with realistic demo content: users with a follower graph,
membership-gated (premium) channels, historical claim/position posts resolved
through the REAL resolution pipeline against real provider OHLC data, live
unresolved content tracked by the observer, and organic-looking engagement.

Run `seed_assets` first so the asset catalog exists. The command is
deterministic for a given --seed and assumes a freshly flushed database.

Usage:
    uv run python manage.py seed_prod
    uv run python manage.py seed_prod --users 20 --resolved-claims 30 \
        --live-claims 10 --positions 20   # quick local smoke run
"""

from __future__ import annotations

import hashlib
import random
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone as django_timezone

from accounts.models import Follow, ProfitabilityCache, WalletUser
from notifications.models import Notification
from posts.asset_providers import get_or_create_asset
from posts.models import (
    Asset,
    AssetSubscription,
    Channel,
    ChannelMembership,
    ClaimMarket,
    ClaimStake,
    HardClaim,
    HardClaimEvent,
    Position,
    PositionEvent,
    Post,
    PostComment,
    PostCommentLike,
    PostLike,
    SavedProof,
)
from posts import rep_market
from posts.ohlc_fetcher import Interval, OHLCFetchError, get_ohlc_data
from posts.position_resolution import resolve_positions
from posts.profitability import recalculate_profitability
from posts.resolution import ResolutionError, resolve_hard_claim


# ---------------------------------------------------------------------------
# Backdating support
# ---------------------------------------------------------------------------

# (model, field_name) pairs whose auto_now_add must be lifted so seeded rows
# can carry historical timestamps. The hardclaim_until_after_created_at check
# constraint makes this mandatory for historical claims, not just cosmetic.
_BACKDATED_FIELDS = [
    (WalletUser, "created_at"),
    (Follow, "created_at"),
    (Channel, "created_at"),
    (ChannelMembership, "created_at"),
    (Post, "created_at"),
    (PostLike, "created_at"),
    (PostComment, "created_at"),
    (PostCommentLike, "created_at"),
    (SavedProof, "created_at"),
    (HardClaim, "created_at"),
    (HardClaimEvent, "timestamp"),
    (Position, "created_at"),
    (PositionEvent, "timestamp"),
]


@contextmanager
def explicit_timestamps():
    """Temporarily disable auto_now_add so create() honours passed timestamps.

    Rows created without an explicit value (e.g. events emitted by the real
    resolution pipeline while seeding) fall back to a now() default.
    """
    fields = [model._meta.get_field(name) for model, name in _BACKDATED_FIELDS]
    saved = [(f, f.auto_now_add, f.default) for f in fields]
    for f in fields:
        f.auto_now_add = False
        f.default = django_timezone.now
    try:
        yield
    finally:
        for f, auto, default in saved:
            f.auto_now_add = auto
            f.default = default


# ---------------------------------------------------------------------------
# Static pools
# ---------------------------------------------------------------------------

USERNAME_FIRST = [
    "macro", "sats", "bist", "alpha", "degen", "chart", "swing", "vol",
    "trend", "delta", "gamma", "hodl", "bear", "bull", "pump", "quant",
    "yield", "perma", "turbo", "borsa", "kripto", "lira", "dolar", "altin",
    "moon", "dip", "fib", "rsi", "wick", "candle",
]
USERNAME_SECOND = [
    "mike", "hunter", "stacker", "wolf", "sniper", "wizard", "guru", "kaplan",
    "trader", "shark", "hawk", "fox", "pasha", "reis", "abi", "usta",
    "kurdu", "master", "lord", "punk", "whale", "ape", "cat", "owl",
]

CHANNEL_POOL = [
    ("Alpha Signals", "Daily high-conviction setups. Entries, stops, targets."),
    ("BIST Radar", "Borsa Istanbul momentum plays and earnings season watchlist."),
    ("Macro Compass", "Rates, FX and the big picture. Weekly outlooks."),
    ("Sats Standard", "Bitcoin-only research. On-chain data and cycle analysis."),
    ("Altcoin Lab", "High-risk high-reward altcoin rotations. DYOR."),
    ("Tech Earnings Desk", "US tech earnings previews and post-print reactions."),
    ("Swing Setups", "Multi-day swing trades with full risk parameters."),
    ("The Short Side", "Bearish theses only. Overvalued names and crowded longs."),
    ("Anadolu Yatirimci", "Uzun vadeli temettu ve deger hisseleri."),
    ("Degen Express", "Leverage, memecoins and pain. Not financial advice."),
    ("Quiet Compounders", "Boring businesses, beautiful charts."),
    ("Options Flow TR", "Unusual options activity and gamma levels."),
    ("Yield Hunters", "Stables, staking and real yield strategies."),
    ("Chart Cafe", "Pure technical analysis. Patterns, levels, volume."),
]

BULLISH_TEMPLATES = [
    "{sym} is coiling for a breakout. I see {pct}% upside by {date}. Position accordingly.",
    "Accumulation on {sym} is textbook. Calling {pct}% up before {date}.",
    "{sym} just reclaimed a key level. {pct}% move incoming — deadline {date}.",
    "Everyone is sleeping on {sym}. {pct}% rally by {date}, screenshot this.",
    "My models flash green on {sym}. Target: +{pct}% by {date}.",
    "{sym} funding reset, weak hands flushed. {pct}% up by {date} is the easy path.",
    "Institutional flows rotating into {sym}. I'm staking rep on +{pct}% before {date}.",
    "Higher lows since weeks on {sym}. Breakout target +{pct}% by {date}.",
    "{sym} narrative is just getting started. +{pct}% by {date}.",
    "Volume profile on {sym} screams continuation. +{pct}% before {date} or I'm wrong.",
]
BEARISH_TEMPLATES = [
    "{sym} is wildly overextended here. {pct}% drawdown by {date}.",
    "Distribution all over the {sym} tape. Calling {pct}% down before {date}.",
    "{sym} bagholders won't like this: -{pct}% by {date}.",
    "Smart money exited {sym} weeks ago. {pct}% lower by {date}.",
    "{sym} chart is a textbook top. -{pct}% before {date}, staking my rep on it.",
    "Liquidity below on {sym} will get taken. -{pct}% by {date}.",
    "The {sym} pump was exit liquidity. Down {pct}% by {date}.",
    "Macro headwinds + ugly chart = {sym} -{pct}% by {date}.",
]
POSITION_TEMPLATES = [
    "Opening a {dir} on {sym}. Entry {entry}, SL {sl}, TP {tp}. Risk managed, conviction high.",
    "{sym} {dir} setup triggered my criteria. Entry {entry} / stop {sl} / target {tp}.",
    "New {dir} position: {sym}. {entry} entry, cutting at {sl}, taking profit at {tp}.",
    "Playing the range on {sym}. {dir} from {entry}, invalidation {sl}, target {tp}.",
    "R:R too good to ignore on {sym}. {dir} @ {entry}, SL {sl}, TP {tp}.",
    "Textbook setup on {sym}. Going {dir} at {entry}. Stop {sl}, target {tp}.",
]
PLAIN_TEMPLATES = [
    "Market breadth is the worst I've seen in months. Stay nimble.",
    "Reminder: position sizing matters more than entries.",
    "CPI week. Reduce leverage or get humbled.",
    "The best trades feel uncomfortable at entry. The worst feel obvious.",
    "Took profits today. Cash is a position too.",
    "Watching the dollar index closely — everything else is noise until it resolves.",
    "BIST volume drying up. Either accumulation or apathy, we'll know soon.",
    "Funding rates back to euphoric levels. You know what comes next.",
    "Patience pays. No setup, no trade.",
    "Earnings season is when narratives meet reality.",
    "Halving cycles don't repeat but they rhyme.",
    "Your edge isn't information anymore, it's discipline.",
    "红包 season for volatility traders. IV is dirt cheap right now.",
    "Unpopular opinion: most of you should just DCA and log off.",
    "Risk happens fast. Hedge accordingly.",
]
COMMENT_TEMPLATES = [
    "Agreed, the chart supports this.",
    "Bold call. Following to see how it plays out.",
    "I'm taking the other side of this one.",
    "What's your invalidation level?",
    "This aged well.",
    "Respect for staking rep on it.",
    "Volume doesn't confirm imo.",
    "Been watching the same level, good catch.",
    "RemindMe when this resolves.",
    "Katiliyorum, grafik cok net.",
    "Bence tam tersi olacak ama gorecegiz.",
    "Hocam bu seviyeden giris mantikli mi?",
    "Finally someone says it.",
    "Source: trust me bro?",
    "The rep market disagrees with you slightly.",
    "Solid risk management on this one.",
    "Counter-argument: macro says no.",
    "I was bearish until I saw this breakdown.",
    "Following you after that last call.",
    "Screenshot taken.",
]
REPLY_TEMPLATES = [
    "Fair point, but the timeframe matters here.",
    "We'll see at resolution.",
    "That's what makes a market.",
    "Invalidation is on the claim itself, check the target.",
    "Haklisin, ama trend trend'dir.",
    "Disagree, liquidity tells a different story.",
    "Time will tell.",
]

# Demo asset universe: symbol -> (market for get_or_create_asset, weight)
CLAIM_ASSETS = [
    ("BTC", "crypto", 22),
    ("ETH", "crypto", 18),
    ("SOL", "crypto", 12),
    ("BNB", "crypto", 6),
    ("XRP", "crypto", 6),
    ("DOGE", "crypto", 6),
    ("AVAX", "crypto", 5),
    ("LINK", "crypto", 5),
    ("AAPL", "nasdaq", 5),
    ("NVDA", "nasdaq", 6),
    ("TSLA", "nasdaq", 5),
    ("THYAO", "bist", 2),
    ("ASELS", "bist", 2),
]

UTC = dt_timezone.utc

# Archetypes: (name, count_weight, hit_rate, posts_weight, follower_weight)
ARCHETYPES = [
    ("influencer", 7, 0.78, 10, 30),
    ("skilled", 17, 0.65, 6, 8),
    ("average", 46, 0.50, 3, 2),
    ("degen", 23, 0.34, 5, 3),
    ("lurker", 7, 0.50, 0, 1),
]


def _fake_address(i: int) -> str:
    return "0x" + hashlib.sha256(f"verifi-demo-{i}".encode()).hexdigest()[:40]


def _midnight(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=UTC)


class Command(BaseCommand):
    help = "Seed the database with realistic demo users, channels, claims, positions and engagement."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=150)
        parser.add_argument("--channels", type=int, default=12)
        parser.add_argument("--resolved-claims", type=int, default=300)
        parser.add_argument("--live-claims", type=int, default=80)
        parser.add_argument("--positions", type=int, default=200)
        parser.add_argument("--plain-posts", type=int, default=80)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **opts):
        self.rng = random.Random(opts["seed"])
        self.now = django_timezone.now()
        self.today = self.now.date()

        self._remove_legacy_fixture_rows()

        with explicit_timestamps():
            users = self._seed_users(opts["users"])
            self._seed_follows(users)
            channels = self._seed_channels(users, opts["channels"])
            assets = self._load_assets()
            resolved_stats = self._seed_resolved_claims(
                users, channels, assets, opts["resolved_claims"]
            )
            self._seed_live_claims(users, channels, assets, opts["live_claims"])
            self._seed_positions(users, channels, assets, opts["positions"])
            self._seed_plain_posts(users, channels, opts["plain_posts"])
            self._seed_engagement(users)

        self._scatter_stake_timestamps()
        self._finalize_users(users)
        self._print_summary(resolved_stats)

    def _remove_legacy_fixture_rows(self):
        """Drop demo rows planted by old data migrations (posts/0007 etc.)."""
        deleted, _ = HardClaim.objects.filter(post=None).delete()
        users_deleted, _ = WalletUser.objects.filter(
            username__in=["user_aabbcc", "user_112233", "user_998877"]
        ).delete()
        if deleted or users_deleted:
            self.stdout.write(
                f"removed legacy fixture rows: {deleted} claim-related, {users_deleted} user-related"
            )

    # -- users ---------------------------------------------------------------

    def _seed_users(self, count: int) -> list[tuple[WalletUser, str]]:
        rng = self.rng
        handles = [f"{a}_{b}" for a in USERNAME_FIRST for b in USERNAME_SECOND]
        rng.shuffle(handles)
        # Dedupe-safe: pool is 30*24=720 unique handles.
        arch_names = [a[0] for a in ARCHETYPES]
        arch_weights = [a[1] for a in ARCHETYPES]

        users: list[tuple[WalletUser, str]] = []
        for i in range(count):
            arch = rng.choices(arch_names, weights=arch_weights)[0]
            created = self.now - timedelta(days=rng.randint(35, 240), hours=rng.randint(0, 23))
            user = WalletUser.objects.create(
                address=_fake_address(i),
                username=handles[i][:30],
                rep=1000.0,  # headroom for market stakes; rescaled in _finalize_users
                energy=float(rng.randint(0, 4)),
                created_at=created,
            )
            users.append((user, arch))
        self.stdout.write(f"users: {len(users)}")
        return users

    def _by_arch(self, users, *names):
        return [u for u, a in users if a in names]

    def _seed_follows(self, users):
        rng = self.rng
        weight_map = {a[0]: a[4] for a in ARCHETYPES}
        targets = [u for u, _ in users]
        target_weights = [weight_map[a] for _, a in users]
        created = 0
        for follower, _arch in users:
            n = rng.randint(3, 25)
            picked = set()
            for _ in range(n):
                target = rng.choices(targets, weights=target_weights)[0]
                if target.pk == follower.pk or target.pk in picked:
                    continue
                picked.add(target.pk)
                start = max(follower.created_at, target.created_at)
                Follow.objects.create(
                    follower=follower,
                    following=target,
                    created_at=start + (self.now - start) * rng.random(),
                )
                created += 1
        self.stdout.write(f"follows: {created}")

    # -- channels ------------------------------------------------------------

    def _seed_channels(self, users, count: int) -> list[Channel]:
        rng = self.rng
        creators = self._by_arch(users, "influencer", "skilled")
        members_pool = [u for u, _ in users]
        channels = []
        for name, desc in rng.sample(CHANNEL_POOL, min(count, len(CHANNEL_POOL))):
            creator = rng.choice(creators)
            chan_created = self.now - timedelta(days=rng.randint(30, 180))
            channel = Channel.objects.create(
                name=name,
                description=desc,
                creator=creator,
                post_permission=(
                    Channel.PostPermission.CREATOR_ONLY
                    if rng.random() < 0.6
                    else Channel.PostPermission.ALL
                ),
                created_at=chan_created,
            )
            ChannelMembership.objects.create(
                channel=channel,
                user=creator,
                status=ChannelMembership.Status.APPROVED,
                role=ChannelMembership.Role.OWNER,
                created_at=chan_created,
            )
            member_count = rng.randint(10, 40)
            pending_count = rng.randint(2, 5)
            picked = rng.sample(
                [u for u in members_pool if u.pk != creator.pk],
                min(member_count + pending_count, len(members_pool) - 1),
            )
            for idx, member in enumerate(picked):
                joined = chan_created + (self.now - chan_created) * rng.random()
                ChannelMembership.objects.create(
                    channel=channel,
                    user=member,
                    status=(
                        ChannelMembership.Status.APPROVED
                        if idx < member_count
                        else ChannelMembership.Status.PENDING
                    ),
                    role=ChannelMembership.Role.MEMBER,
                    created_at=joined,
                )
            channels.append(channel)
        self.stdout.write(f"channels: {len(channels)}")
        return channels

    # -- assets ----------------------------------------------------------------

    def _load_assets(self) -> list[tuple[Asset, int]]:
        out = []
        name_map = {
            "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "BNB": "BNB",
            "XRP": "XRP", "DOGE": "Dogecoin", "AVAX": "Avalanche", "LINK": "Chainlink",
            "AAPL": "Apple Inc", "NVDA": "NVIDIA", "TSLA": "Tesla",
            "THYAO": "Turk Hava Yollari", "ASELS": "Aselsan",
        }
        # Heuristic coingecko id (base.lower()) is wrong for several majors, so
        # spell the ids out for the fallback-create path. Existing catalog rows
        # from seed_assets are reused untouched.
        coingecko_ids = {
            "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
            "BNB": "binancecoin", "XRP": "ripple", "DOGE": "dogecoin",
            "AVAX": "avalanche-2", "LINK": "chainlink",
        }
        market_type_map = {
            "crypto": Asset.MarketType.CRYPTO,
            "nasdaq": Asset.MarketType.EQUITY,
            "bist": Asset.MarketType.EQUITY,
        }
        for symbol, market, weight in CLAIM_ASSETS:
            asset = Asset.objects.filter(
                symbol=symbol, market_type=market_type_map[market]
            ).first()
            if asset is None:
                asset, _ = get_or_create_asset(
                    symbol=symbol,
                    name=name_map.get(symbol, symbol),
                    market=market,
                    coingecko_id=coingecko_ids.get(symbol),
                )
            out.append((asset, weight))
        return out

    def _pick_asset(self, assets) -> Asset:
        return self.rng.choices(
            [a for a, _ in assets], weights=[w for _, w in assets]
        )[0]

    def _claim_ohlc(self, asset: Asset, start_day: date, end_day: date):
        """Daily candles for [start_day, end_day] via the cached fetcher."""
        try:
            return get_ohlc_data(
                asset,
                _midnight(start_day),
                _midnight(end_day + timedelta(days=1)),
                mixed_resolution=True,
            )
        except OHLCFetchError:
            return []

    # -- authoring helpers -----------------------------------------------------

    def _pick_author(self, users) -> tuple[WalletUser, str]:
        weight_map = {a[0]: a[3] for a in ARCHETYPES}
        weights = [weight_map[arch] for _, arch in users]
        return self.rng.choices(users, weights=weights)[0]

    def _maybe_channel(self, author: WalletUser, channels) -> Channel | None:
        """~25% of posts land in a channel the author can post to."""
        if self.rng.random() > 0.25:
            return None
        own = [c for c in channels if c.creator_id == author.pk]
        open_membership = [
            c for c in channels
            if c.post_permission == Channel.PostPermission.ALL
            and ChannelMembership.objects.filter(
                channel=c, user=author, status=ChannelMembership.Status.APPROVED
            ).exists()
        ]
        options = own + open_membership
        return self.rng.choice(options) if options else None

    def _hit_rate(self, arch: str) -> float:
        return {a[0]: a[2] for a in ARCHETYPES}[arch]

    # -- resolved historical claims --------------------------------------------

    def _seed_resolved_claims(self, users, channels, assets, count: int) -> dict:
        rng = self.rng
        stats = {"confirmed": 0, "rejected": 0, "failed": 0, "skipped": 0}
        for _ in range(count):
            author, arch = self._pick_author(users)
            asset = self._pick_asset(assets)

            created_day = self.today - timedelta(days=rng.randint(21, 180))
            horizon = rng.randint(7, min(60, (self.today - created_day).days - 2))
            until = created_day + timedelta(days=horizon)
            created_at = _midnight(created_day)

            rows = self._claim_ohlc(asset, created_day, until)
            if not rows:
                stats["skipped"] += 1
                continue
            reference = rows[0].open
            if reference <= 0:
                stats["skipped"] += 1
                continue

            direction = "bullish" if rng.random() < 0.62 else "bearish"
            if direction == "bullish":
                favorable = (max(c.high for c in rows) - reference) / reference * 100
            else:
                favorable = (reference - min(c.low for c in rows)) / reference * 100
            favorable = max(favorable, 0.0)

            want_hit = rng.random() < self._hit_rate(arch)
            if want_hit and favorable >= 1.0:
                pct = favorable * rng.uniform(0.40, 0.85)
            else:
                pct = max(favorable, 0.5) * rng.uniform(1.25, 2.5)
            pct = round(min(max(pct, 0.5), 90.0), 1)

            templates = BULLISH_TEMPLATES if direction == "bullish" else BEARISH_TEMPLATES
            content = rng.choice(templates).format(
                sym=asset.symbol, pct=pct, date=until.strftime("%d %b %Y")
            )
            channel = self._maybe_channel(author, channels)
            post = Post.objects.create(
                author=author, channel=channel, content=content, created_at=created_at
            )
            claim = HardClaim.objects.create(
                author=author,
                post=post,
                channel=channel,
                asset=asset,
                direction=direction,
                value_type="PERCENTAGE_UP",
                percentage=pct,
                until=until,
                status=HardClaim.Status.UNDETERMINED,
                reference_price=round(reference, 2),
                reference_price_url="seeded_ohlc_open",
                created_at=created_at,
            )
            HardClaimEvent.objects.create(
                hard_claim=claim,
                event_type=HardClaimEvent.EventType.CREATION,
                timestamp=created_at,
                details={
                    "reference_price": round(reference, 2),
                    "reference_url": "seeded_ohlc_open",
                    "reference_at": created_at.isoformat(),
                },
            )

            if rng.random() < 0.6:
                self._open_market(claim, author, users)

            try:
                result = resolve_hard_claim(claim)
                stats[result["status"]] += 1
            except (ResolutionError, OHLCFetchError) as exc:
                stats["failed"] += 1
                self.stderr.write(f"claim {claim.id} ({asset.symbol}) unresolved: {exc}")

        self.stdout.write(
            f"resolved claims: {stats['confirmed']} confirmed / {stats['rejected']} rejected "
            f"({stats['failed']} failed, {stats['skipped']} skipped)"
        )
        return stats

    def _open_market(self, claim: HardClaim, author: WalletUser, users):
        rng = self.rng
        side = "YES" if rng.random() < 0.85 else "NO"
        try:
            market = rep_market.init_market(
                claim, author, side, float(rng.randint(10, 60))
            )
        except rep_market.MarketError:
            return
        stakers = rng.sample(
            [u for u, _ in users if u.pk != author.pk], rng.randint(0, 8)
        )
        for staker in stakers:
            try:
                rep_market.buy(market, staker, "YES" if rng.random() < 0.5 else "NO")
            except rep_market.MarketError:
                continue

    # -- live claims -------------------------------------------------------------

    def _seed_live_claims(self, users, channels, assets, count: int):
        rng = self.rng
        created_n = 0
        for _ in range(count):
            author, _arch = self._pick_author(users)
            asset = self._pick_asset(assets)
            created_day = self.today - timedelta(days=rng.randint(1, 7))
            created_at = _midnight(created_day)
            until = self.today + timedelta(days=rng.randint(7, 90))

            rows = self._claim_ohlc(asset, created_day, min(self.today, created_day + timedelta(days=2)))
            if not rows:
                continue
            reference = rows[0].open

            direction = "bullish" if rng.random() < 0.6 else "bearish"
            pct = round(rng.uniform(2.0, 35.0), 1)
            templates = BULLISH_TEMPLATES if direction == "bullish" else BEARISH_TEMPLATES
            content = rng.choice(templates).format(
                sym=asset.symbol, pct=pct, date=until.strftime("%d %b %Y")
            )
            channel = self._maybe_channel(author, channels)
            post = Post.objects.create(
                author=author, channel=channel, content=content, created_at=created_at
            )
            claim = HardClaim.objects.create(
                author=author,
                post=post,
                channel=channel,
                asset=asset,
                direction=direction,
                value_type="PERCENTAGE_UP",
                percentage=pct,
                until=until,
                status=HardClaim.Status.UNDETERMINED,
                reference_price=round(reference, 2),
                reference_price_url="seeded_ohlc_open",
                created_at=created_at,
            )
            HardClaimEvent.objects.create(
                hard_claim=claim,
                event_type=HardClaimEvent.EventType.CREATION,
                timestamp=created_at,
                details={
                    "reference_price": round(reference, 2),
                    "reference_url": "seeded_ohlc_open",
                    "reference_at": created_at.isoformat(),
                },
            )
            AssetSubscription.objects.create(asset=asset, hard_claim=claim)
            if rng.random() < 0.5:
                self._open_market(claim, author, users)
            created_n += 1
        self.stdout.write(f"live claims: {created_n}")

    # -- positions -----------------------------------------------------------------

    def _seed_positions(self, users, channels, assets, count: int):
        rng = self.rng
        historical = int(count * 0.7)
        created_n = 0
        for i in range(count):
            author, arch = self._pick_author(users)
            asset = self._pick_asset(assets)
            is_historical = i < historical

            if is_historical:
                created_day = self.today - timedelta(days=rng.randint(20, 170))
            else:
                created_day = self.today - timedelta(days=rng.randint(0, 5))
            created_at = _midnight(created_day)

            rows = self._claim_ohlc(
                asset, created_day, min(self.today, created_day + timedelta(days=3))
            )
            if not rows:
                continue
            base = rows[0].open

            direction = (
                Position.Direction.LONG if rng.random() < 0.65 else Position.Direction.SHORT
            )
            skilled = rng.random() < self._hit_rate(arch)
            # Entry sits just inside the expected first-day range so most
            # positions trigger; SL/TP widths shape the outcome odds.
            if direction == Position.Direction.LONG:
                entry = base * rng.uniform(0.985, 0.999)
                sl_pct = rng.uniform(0.03, 0.10) if skilled else rng.uniform(0.015, 0.05)
                tp_pct = rng.uniform(0.03, 0.08) if skilled else rng.uniform(0.08, 0.25)
                sl = entry * (1 - sl_pct)
                tp = entry * (1 + tp_pct)
            else:
                entry = base * rng.uniform(1.001, 1.015)
                sl_pct = rng.uniform(0.03, 0.10) if skilled else rng.uniform(0.015, 0.05)
                tp_pct = rng.uniform(0.03, 0.08) if skilled else rng.uniform(0.08, 0.25)
                sl = entry * (1 + sl_pct)
                tp = entry * (1 - tp_pct)

            entry_interval = _midnight(created_day + timedelta(days=rng.randint(3, 10)))
            lifetime = entry_interval + timedelta(days=rng.randint(10, 45))

            content = rng.choice(POSITION_TEMPLATES).format(
                dir=direction.upper(),
                sym=asset.symbol,
                entry=f"{entry:,.2f}",
                sl=f"{sl:,.2f}",
                tp=f"{tp:,.2f}",
            )
            channel = self._maybe_channel(author, channels)
            post = Post.objects.create(
                author=author, channel=channel, content=content, created_at=created_at
            )
            position = Position.objects.create(
                author=author,
                channel=channel,
                post=post,
                asset=asset,
                direction=direction,
                entry_price=round(entry, 2),
                entry_interval=entry_interval,
                stop_loss=round(sl, 2),
                take_profit=round(tp, 2),
                lifetime=lifetime,
                status=Position.Status.PENDING,
                created_at=created_at,
            )
            PositionEvent.objects.create(
                position=position,
                event_type=PositionEvent.EventType.CREATION,
                timestamp=created_at,
                details={"message": "Position created with post"},
            )
            created_n += 1

        # Run the real two-phase resolver over everything pending/active.
        # Historical positions resolve against real candles; live ones either
        # activate or stay pending.
        resolve_positions()

        live_open = Position.objects.filter(
            status__in=[Position.Status.PENDING, Position.Status.ACTIVE]
        )
        for pos in live_open:
            AssetSubscription.objects.get_or_create(
                position=pos, defaults={"asset": pos.asset}
            )

        from django.db.models import Count
        breakdown = dict(
            Position.objects.values_list("status").annotate(n=Count("id"))
        )
        self.stdout.write(f"positions: {created_n} created, statuses: {breakdown}")

    # -- plain posts -------------------------------------------------------------

    def _seed_plain_posts(self, users, channels, count: int):
        rng = self.rng
        for _ in range(count):
            author, _arch = self._pick_author(users)
            created = self.now - timedelta(
                days=rng.randint(0, 150), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
            )
            if created < author.created_at:
                created = author.created_at + timedelta(hours=1)
            Post.objects.create(
                author=author,
                channel=self._maybe_channel(author, channels),
                content=rng.choice(PLAIN_TEMPLATES),
                created_at=created,
            )
        self.stdout.write(f"plain posts: {count}")

    # -- engagement -------------------------------------------------------------

    def _seed_engagement(self, users):
        rng = self.rng
        all_users = [u for u, _ in users]
        arch_by_pk = {u.pk: a for u, a in users}
        likes = comments = clikes = saves = 0

        confirmed_post_ids = set(
            HardClaim.objects.filter(status=HardClaim.Status.CONFIRMED)
            .exclude(post=None)
            .values_list("post_id", flat=True)
        )

        for post in Post.objects.select_related("author").all():
            author_arch = arch_by_pk.get(post.author_id, "average")
            hotness = {"influencer": 35, "skilled": 18, "average": 7, "degen": 10, "lurker": 4}[
                author_arch
            ]
            window_end = min(self.now, post.created_at + timedelta(days=14))

            def ts():
                return post.created_at + (window_end - post.created_at) * rng.random()

            for user in rng.sample(all_users, min(rng.randint(0, hotness), len(all_users))):
                if user.pk == post.author_id:
                    continue
                PostLike.objects.create(post=post, user=user, created_at=ts())
                likes += 1

            post_comments = []
            for _ in range(rng.randint(0, max(2, hotness // 3))):
                commenter = rng.choice(all_users)
                comment = PostComment.objects.create(
                    post=post,
                    author=commenter,
                    content=rng.choice(COMMENT_TEMPLATES),
                    created_at=ts(),
                )
                post_comments.append(comment)
                comments += 1
                if rng.random() < 0.3:
                    PostComment.objects.create(
                        post=post,
                        parent=comment,
                        author=rng.choice(all_users),
                        content=rng.choice(REPLY_TEMPLATES),
                        created_at=min(comment.created_at + timedelta(hours=rng.randint(1, 48)), self.now),
                    )
                    comments += 1

            for comment in post_comments:
                for user in rng.sample(all_users, rng.randint(0, 4)):
                    if PostCommentLike.objects.filter(comment=comment, user=user).exists():
                        continue
                    PostCommentLike.objects.create(comment=comment, user=user, created_at=ts())
                    clikes += 1

            save_odds = 0.5 if post.id in confirmed_post_ids else 0.06
            if rng.random() < save_odds:
                for user in rng.sample(all_users, rng.randint(1, 6)):
                    SavedProof.objects.create(post=post, user=user, created_at=ts())
                    saves += 1

        self.stdout.write(
            f"engagement: {likes} likes, {comments} comments, {clikes} comment likes, {saves} saved proofs"
        )

    # -- finalization -------------------------------------------------------------

    def _scatter_stake_timestamps(self):
        """ClaimStake.created_at can't be passed through buy(); backdate after."""
        rng = self.rng
        for stake in ClaimStake.objects.select_related("market__hard_claim").all():
            claim = stake.market.hard_claim
            start = claim.created_at
            end = min(_midnight(claim.until), self.now)
            if end <= start:
                end = start + timedelta(hours=1)
            ClaimStake.objects.filter(pk=stake.pk).update(
                created_at=start + (end - start) * rng.random()
            )

    def _finalize_users(self, users):
        """Rescale rep into a believable range, preserving market-driven order."""
        for user, _arch in users:
            user.refresh_from_db()
        reps = [u.rep for u, _ in users]
        lo, hi = min(reps), max(reps)
        spread = (hi - lo) or 1.0
        for user, _arch in users:
            scaled = 80.0 + (user.rep - lo) / spread * 720.0
            user.rep = round(scaled, 1)
            user.save(update_fields=["rep"])
            recalculate_profitability(user)
        self.stdout.write("profitability cache rebuilt, rep rescaled to 80-800")

    def _print_summary(self, resolved_stats):
        self.stdout.write(self.style.SUCCESS("--- seed summary ---"))
        for label, qs in [
            ("users", WalletUser.objects),
            ("follows", Follow.objects),
            ("channels", Channel.objects),
            ("memberships", ChannelMembership.objects),
            ("posts", Post.objects),
            ("hard claims", HardClaim.objects),
            ("  confirmed", HardClaim.objects.filter(status="confirmed")),
            ("  rejected", HardClaim.objects.filter(status="rejected")),
            ("  undetermined", HardClaim.objects.filter(status="undetermined")),
            ("positions", Position.objects),
            ("markets", ClaimMarket.objects),
            ("stakes", ClaimStake.objects),
            ("subscriptions", AssetSubscription.objects),
            ("likes", PostLike.objects),
            ("comments", PostComment.objects),
            ("saved proofs", SavedProof.objects),
            ("notifications", Notification.objects),
            ("profitability rows", ProfitabilityCache.objects),
        ]:
            self.stdout.write(f"{label}: {qs.count()}")
