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

# Mixed handle styles so the user list doesn't look generated: snake_case,
# CamelCase, lowercase mashups, plain names, numbers, Turkish + English.
HANDLES = [
    "MacroMike", "sats_stacker", "bullrun2024", "denizyilmaz", "fibwhisperer",
    "CryptoEmre", "zeynep_fx", "TheChartGuy", "mr_volatility", "kerem",
    "aysetrades", "BISTkaplani", "JLinCapital", "wickcatcher", "perma_bear_ali",
    "GammaGoblin", "selin", "hodlferatu", "trader_joe61", "altinci_his",
    "DegenDede", "liquidity_hunter", "Mehmet_K", "noisetrader", "OnurFX",
    "candlewitch", "borsa_kurdu_35", "QuantQueen", "dipbuyer99", "ekremabi",
    "SwingState", "tugce_charts", "blokzincirci", "TheRealHODL", "mertcan",
    "VWAPyilmaz", "shortsqueezer", "Aslihan", "satoshi_torunu", "breadthwatch",
    "Ece_Macro", "rsi_dervisi", "ChartCemil", "yieldfarmer_x", "B2Bderya",
    "TurboTunc", "ihtiyatli_ayi", "moon_misafiri", "DrDrawdown", "haticeFX",
    "pivot_pasa", "LeylaLong", "stop_avcisi", "GokhanGamma", "tape_reader",
    "umutlu_boga", "FonFatihi", "cembektas", "thetagang_tr", "KriptoKaan",
    "sessiz_balina", "OrderFlowOzge", "fakeout_fatih", "Yigit", "marjin_magduru",
    "ButterflyBurak", "ons_altinci", "ScalperSerkan", "duygusal_yatirimci",
    "HalukHedge", "trend_takipcisi", "irem_invests", "BetaBilal", "carrytrade",
    "kagit_elli", "DovizDoktoru", "basebreaker", "Nazli_N", "volkan_vol",
    "front_runner61", "EnflasyonEnes", "supportbecameresistance", "ozlem",
    "AyiPiyasasi", "rangebound", "Cagri_Capital", "likidite_avi", "muratbey",
    "SeranSwing", "grafik_delisi", "TahvilTayfun", "elifce", "drawdown_dayi",
    "PnLPelin", "acik_pozisyon", "BernaBreakout", "temettucu", "harunFX",
    "zarar_kes", "MomentumMine", "yatay_seyir", "Koray_K", "balina_izci",
    "FundingFunda", "tersine_yatirimci", "SinemSpot", "cekic_formasyonu",
    "uzun_vadeci", "EmirEmtia", "piyasa_turisti", "hilal_trades", "BogaBaran",
    "islemci", "KaldiracKurbani", "sabirli_yatirimci", "DilaraDip", "ahmet_61",
    "okkesabi", "TrendTeyze", "realized_loss", "merve_makro", "SpotSuat",
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
    "ok im just gonna say it. {sym} +{pct}% by {date}. been staring at this chart all week and the setup is identical to last october",
    "loaded up on more {sym} today 🤝 target is +{pct}% before {date}, see you there",
    "{sym} weekly close was beautiful. calling it now — {pct}% up by {date}",
    "everyone fading {sym} rn which is exactly why im not. +{pct}% by {date} and yes im staking rep on it",
    "cant sleep so i charted {sym} again lol. anyway, +{pct}% by {date}. screenshot this",
    "the {sym} accumulation phase is done imo. next leg starts now. +{pct}% by {date} 📈",
    "abi {sym} resmen kaciyor. {date} tarihine kadar +%{pct} gorurum diyorum, yazin bir kenara",
    "{sym} hala ucuz. {date} olmadan +{pct}% bekliyorum, gerisi hikaye",
    "unpopular take maybe but {sym} is the cleanest chart on my whole watchlist. +{pct}% by {date}",
    "if {sym} holds this level we see +{pct}% by {date}. if not, well... lets not think about that",
    "third time testing this resistance. {sym} breaks it this time. +{pct}% by {date}",
    "my {sym} thesis hasnt changed in months. flows + supply squeeze = +{pct}% before {date}",
    "was bearish on {sym} until this morning. flipped. +{pct}% by {date}, dont @ me",
    "quietly accumulating {sym} while everyone argues on the timeline. +{pct}% by {date} is my line in the sand",
    "{sym} grafigine bakan herkes ayni seyi goruyor ama kimse yazmiyor 🙂 {date} kadar +%{pct}",
    "not a single bearish divergence on {sym} anywhere. {pct}% upside minimum by {date}",
    "remember when they laughed at my last {sym} call? +{pct}% by {date}. running it back",
    "ok hear me out: {sym}, +{pct}%, {date}. thats it. thats the post",
]
BEARISH_TEMPLATES = [
    "sorry but {sym} looks terrible here. -{pct}% by {date} and im not even being dramatic",
    "took one look at {sym} funding and went short. -{pct}% by {date} 🐻",
    "{sym} holders dont want to hear this but distribution started weeks ago. {pct}% down by {date}",
    "everything about this {sym} pump screams exit liquidity. -{pct}% before {date}",
    "{sym} dusecek diyorum, bana kizacaksiniz ama grafik ortada. {date} kadar -%{pct}",
    "im short {sym}. crowded long, weak breadth, ugly macro. -{pct}% by {date}",
    "that {sym} wick yesterday? that was the top. -{pct}% by {date}",
    "no shot {sym} holds these levels into {date}. -{pct}% minimum, probably more",
    "the higher {sym} goes the heavier it looks. fading the euphoria, -{pct}% by {date}",
    "called the last two {sym} tops, calling this one too. -{pct}% before {date}",
    "{sym} icin kotu haberim var arkadaslar... {date} kadar -%{pct}. sonra agla(ma)yin",
    "everyone is max long {sym} which historically ends one way. -{pct}% by {date}",
    "this {sym} rally has zero volume behind it. -{pct}% by {date} when reality hits",
]
POSITION_TEMPLATES = [
    "entered {dir} on {sym} at {entry}. stop {sl}, target {tp}. lets see how it goes",
    "couldnt resist this {sym} setup 🎯 {dir} @ {entry}, sl {sl}, tp {tp}",
    "{sym} {dir} from {entry}. invalidation at {sl}. if we tag {tp} drinks are on me",
    "risking 1 to make 3 on {sym}. {dir} entry {entry} / stop {sl} / target {tp}",
    "{dir} {sym} at {entry}. sl {sl}, tp {tp}. boring trade, good trade",
    "girdim {sym} {dir} pozisyonuna, {entry} seviyesinden. stop {sl}, hedef {tp}. hayirlisi 🙏",
    "been waiting two weeks for this {sym} entry. {dir} @ {entry}, stop {sl}, target {tp}",
    "small {dir} on {sym} here ({entry}). tight stop at {sl}, letting it run to {tp}",
    "new position: {sym} {dir}. entry {entry}, cut at {sl}, take profit {tp}. posting so i dont chicken out",
]
PLAIN_TEMPLATES = [
    "market breadth is the worst ive seen in months. stay nimble out there",
    "reminder: position sizing matters more than your entry. learned this the expensive way",
    "cpi week. cut the leverage or get humbled, your choice",
    "the best trades feel uncomfortable at entry. the obvious ones are usually traps",
    "took profits today. cash is a position too and nobody can convince me otherwise",
    "watching dxy like a hawk, everything else is noise until it resolves",
    "bist hacmi iyice kurudu. ya birikim ya ilgisizlik, yakinda ogrenecegiz",
    "funding rates back at euphoric levels... you all know what happens next",
    "no setup no trade. third day flat and honestly? peaceful",
    "earnings season is when narratives meet reality. bring popcorn",
    "halving cycles dont repeat but they sure do rhyme",
    "your edge isnt information anymore. its discipline. that's the whole tweet",
    "most of you should genuinely just DCA and log off (affectionate)",
    "risk happens fast. hedged this morning, sleeping fine tonight",
    "kar realizasyonu yapan herkese saygi duyuyorum, fomo ile alan herkese gecmis olsun",
    "got stopped out twice today. market said humility and i listened",
    "the chart doesnt care about your feelings. plan the trade, trade the plan",
    "imagine checking your portfolio on a sunday. anyway. how's everyone doing",
    "longest ive gone without a trade this year. edge comes to those who wait",
    "piyasada en pahali sey acele etmek. ikinci en pahali sey beklememek 🙂",
]
COMMENT_TEMPLATES = [
    "agreed, chart supports this",
    "bold call. following to see how it plays out",
    "im taking the other side of this one tbh",
    "whats your invalidation?",
    "this aged well lol",
    "respect for staking rep on it 🫡",
    "volume doesnt confirm imo",
    "been watching the same level, good catch",
    "remindme when this resolves",
    "katiliyorum, grafik cok net",
    "bence tam tersi olacak ama gorecegiz",
    "hocam bu seviyeden giris mantikli mi?",
    "finally someone says it",
    "source: trust me bro?",
    "the rep market slightly disagrees with you 👀",
    "solid risk management on this one",
    "counter: macro says no",
    "i was bearish until i saw this breakdown ngl",
    "followed after that last call of yours",
    "screenshot taken 📸",
    "ser this is a wendy's",
    "kac kez ayni seyi yazdin ama bu sefer hakli olabilirsin",
    "what timeframe is this on?",
    "least delusional fintwit poster",
    "ok but what if youre wrong tho",
    "adding this to my watchlist, thanks",
    "bunu kaydediyorum, resolution gunu konusuruz 😄",
    "your last 3 calls hit so im listening",
    "the audacity of this call lmao. staked NO",
    "underrated post",
    "im in. dont make me regret this",
    "ne zamandir takip ediyorum, isabetli adamsin",
]
REPLY_TEMPLATES = [
    "fair point but the timeframe matters here",
    "we'll see at resolution 🤝",
    "thats what makes a market",
    "invalidation is on the claim itself, check the target",
    "haklisin ama trend trend'dir",
    "disagree, liquidity tells a different story",
    "time will tell",
    "!remindme 30 days",
    "lol ok we'll bookmark this exchange",
    "respectfully, no",
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


# ---------------------------------------------------------------------------
# Images (avatars + chart screenshots), all best-effort
# ---------------------------------------------------------------------------

def _upload_to_cloudinary(source, public_id: str) -> str | None:
    """Upload a remote URL or file-like object; return public_id or None."""
    try:
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            source, public_id=public_id, overwrite=True, resource_type="image"
        )
        return result["public_id"]
    except Exception as exc:  # network/quota failures must not kill the seed
        import logging
        logging.getLogger(__name__).warning("cloudinary upload failed for %s: %s", public_id, exc)
        return None


def _avatar_source(rng: random.Random, username: str) -> str:
    """Photo-ish or illustrated avatar URL, varied per user."""
    roll = rng.random()
    if roll < 0.45:
        return f"https://i.pravatar.cc/400?img={rng.randint(1, 70)}"
    style = rng.choice(["notionists", "adventurer", "bottts", "thumbs", "avataaars"])
    return f"https://api.dicebear.com/9.x/{style}/png?seed={username}&size=400"


def _render_chart_png(asset, rows, target_price: float | None, reference_price: float | None):
    """Dark-theme daily candle chart like a trader's screenshot. Returns PNG bytes."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    if len(rows) < 5:
        return None

    bg, grid_c = "#0d1117", "#21262d"
    up_c, down_c = "#26a69a", "#ef5350"
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=110)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    for x, c in enumerate(rows):
        color = up_c if c.close >= c.open else down_c
        ax.vlines(x, c.low, c.high, color=color, linewidth=1)
        ax.vlines(x, min(c.open, c.close), max(c.open, c.close), color=color, linewidth=4)

    if target_price:
        ax.axhline(target_price, color="#f0b429", linestyle="--", linewidth=1.2)
        ax.annotate(
            f"target {target_price:,.2f}", xy=(0.01, target_price),
            xycoords=("axes fraction", "data"), color="#f0b429",
            fontsize=8, va="bottom",
        )
    if reference_price:
        ax.axhline(reference_price, color="#8b949e", linestyle=":", linewidth=1)

    ax.set_title(
        f"{asset.symbol}/{asset.quote_currency} · 1D",
        color="#c9d1d9", fontsize=11, loc="left",
    )
    ax.grid(color=grid_c, linewidth=0.5, alpha=0.6)
    ax.tick_params(colors="#8b949e", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(grid_c)
    ax.set_xticks([])
    fig.tight_layout()

    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=bg)
    plt.close(fig)
    buf.seek(0)
    return buf


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
        parser.add_argument(
            "--no-images", action="store_true",
            help="Skip avatar/chart uploads (faster local runs).",
        )

    def handle(self, *args, **opts):
        self.rng = random.Random(opts["seed"])
        self.now = django_timezone.now()
        self.today = self.now.date()
        self.with_images = not opts["no_images"]

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
        handles = list(HANDLES)
        rng.shuffle(handles)
        # Overflow past the curated pool gets a numbered suffix.
        while len(handles) < count:
            handles.append(f"{rng.choice(HANDLES)}{rng.randint(2, 99)}")
        arch_names = [a[0] for a in ARCHETYPES]
        arch_weights = [a[1] for a in ARCHETYPES]
        # Avatar coverage by archetype — influencers always have one, lurkers rarely.
        avatar_odds = {"influencer": 1.0, "skilled": 0.85, "average": 0.55, "degen": 0.6, "lurker": 0.25}

        users: list[tuple[WalletUser, str]] = []
        avatars = 0
        for i in range(count):
            arch = rng.choices(arch_names, weights=arch_weights)[0]
            created = self.now - timedelta(days=rng.randint(35, 240), hours=rng.randint(0, 23))
            username = handles[i][:30]
            user = WalletUser.objects.create(
                address=_fake_address(i),
                username=username,
                rep=1000.0,  # headroom for market stakes; rescaled in _finalize_users
                energy=float(rng.randint(0, 4)),
                created_at=created,
            )
            if self.with_images and rng.random() < avatar_odds[arch]:
                public_id = _upload_to_cloudinary(
                    _avatar_source(rng, username), f"seed/avatars/{username}"
                )
                if public_id:
                    user.avatar = public_id
                    user.save(update_fields=["avatar"])
                    avatars += 1
            users.append((user, arch))
        self.stdout.write(f"users: {len(users)} ({avatars} with avatars)")
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

    def _maybe_attach_chart(self, post, asset, created_day, *, target=None, reference=None, odds=0.3):
        """Attach a 'trader screenshot' built from candles BEFORE the post date."""
        if not self.with_images or self.rng.random() > odds:
            return
        lookback = self._claim_ohlc(
            asset, created_day - timedelta(days=self.rng.randint(45, 90)), created_day - timedelta(days=1)
        )
        buf = _render_chart_png(asset, lookback, target, reference)
        if buf is None:
            return
        public_id = _upload_to_cloudinary(buf, f"seed/charts/post-{post.id}")
        if public_id:
            post.image = public_id
            post.save(update_fields=["image"])

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
            target_price = (
                reference * (1 + pct / 100) if direction == "bullish"
                else reference * (1 - pct / 100)
            )
            self._maybe_attach_chart(
                post, asset, created_day, target=target_price, reference=reference
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
            target_price = (
                reference * (1 + pct / 100) if direction == "bullish"
                else reference * (1 - pct / 100)
            )
            self._maybe_attach_chart(
                post, asset, created_day, target=target_price, reference=reference
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
                dir=direction,
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
            self._maybe_attach_chart(
                post, asset, created_day, target=position.take_profit,
                reference=position.entry_price, odds=0.25,
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
