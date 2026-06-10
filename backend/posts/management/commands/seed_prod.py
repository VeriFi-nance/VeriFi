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
    "everyone is doom posting about the iran headlines which is exactly when you buy {sym}. +{pct}% by {date}",
    "bear market is over, you just dont know it yet. {sym} +{pct}% by {date}",
]
# Asset-class flavored extras so crypto memes don't land on AAPL claims.
BULLISH_CRYPTO_EXTRA = [
    "etf outflows slowing, miners done capitulating, funding negative. {sym} +{pct}% by {date}. bottom is a process and the process is over",
    "saylor stopped posting which historically means we're close to the bottom. {sym} +{pct}% by {date}",
    "tom lee just reiterated his target so naturally im scared, but the {sym} chart says +{pct}% by {date} anyway",
    "everyone who survived this bear market deserves the {sym} +{pct}% candle coming before {date}",
]
BULLISH_EQUITY_EXTRA = [
    "ai capex supercycle is NOT slowing down whatever the bears say. {sym} +{pct}% by {date}",
    "every earnings call says 'ai' 47 times and guides up. {sym} +{pct}% by {date}, the hype is the fundamentals now",
    "defense + energy rotation from the gulf tension lands in {sym} eventually. +{pct}% by {date}",
]
BEARISH_CRYPTO_EXTRA = [
    "mstr selling, etf outflows, miners capitulating. {sym} -{pct}% by {date}, sorry",
    "when the biggest corporate holder becomes a seller you dont knife catch. {sym} -{pct}% by {date}",
    "bear market rallies exist to hurt you specifically. {sym} -{pct}% by {date}",
]
BEARISH_EQUITY_EXTRA = [
    "ai hype is priced into {sym} three times over. -{pct}% by {date} when the capex questions start",
    "if hormuz actually closes, {sym} is collateral damage. -{pct}% by {date}",
    "nasdaq is 7 stocks selling ai to each other and {sym} blinks first. -{pct}% by {date}",
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
    "3 monitors, 14 indicators, still entered on vibes. we are not the same",
    "weekly candle close tonight. nobody breathe",
    "deleted my portfolio tracker app. happiness has increased 40% (unrealized)",
    "lesson from this week: the market can stay irrational longer than you can stay awake",
    "kahveyi aldim, grafikleri actim, hayirli islemler herkese ☕",
    "hot take: your watchlist is too long. pick 5 names and actually learn them",
    "the amount of conviction in my feed today is making me nervous ngl",
    "trade journal entry #847: i am once again asking myself why i entered that",
    "green day. saying nothing else, dont want to jinx it",
    "fed day tomorrow. flat going in, no hero trades",
    "iki gundur islem yok, sadece izliyorum. bazen en iyi pozisyon hic pozisyon",
    "if you cant explain your trade in one sentence you dont have a trade",
    "shoutout to everyone who held through that wick. character development",
    "yeni baslayanlara tavsiyem: ilk 6 ay kucuk oyna, ders parasi pesin odenir",
    "real ones know the best chart is the one you didnt trade",
    "my best month this year was the one where i traded the least. let that sink in",
    "liquidity is a social construct until your stop gets hunted",
    "okudugum en iyi yatirim kitabi hala kendi islem gecmisim. aci ama ogretici",
    "weekend chart review done. 2 setups for next week, both need confirmation first",
    "everyone is a genius until the market opens",
    "bugun hic bakmiyorum grafiklere. aile gunu. (3 kere baktim)",
    "less leverage, more sleep. thats the alpha nobody posts about",
    "that feeling when your stop loss saves you from a 20% drawdown 🫡 respect the process",
    "market doesnt know you exist. trade accordingly",
    "the fact that MSTR is selling btc to fund the dividend should radicalize you a little",
    "saylor went from 'bitcoin is hope' to quietly trimming the stack. nature is healing i guess",
    "tom lee year-end target unchanged again. respect the commitment to the bit honestly",
    "nasdaq is 7 companies in a trenchcoat and all 7 are selling AI to each other",
    "my ai agent rebalanced my portfolio into 100% NVDA overnight. i did not ask for this",
    "us iran headlines moving oil 4% premarket AGAIN. love trading geopolitics (i hate trading geopolitics)",
    "hormuz haberleri yine dustu, brent gapliyor, risk-off... ve ben tabii ki longdayim 🤡",
    "yapay zeka isimi alacakmis. alsin kardesim, zararlar da onun olsun artik",
    "mstr satiyor, saylor sustu, tom lee hala ayni hedefi soyluyor. sirk tam kadro sahnede",
    "everyone's an ai company now. my barber put 'powered by AI' on his window. he cuts hair",
    "btc down bad and my uber driver stopped pitching me coins. historically a bottom signal",
    "bear market survival guide: 1) log off 2) thats it",
    "ai bubble or new paradigm? por que no los dos",
    "imagine surviving the whole bear market just to get liquidated on the recovery wick",
    "fed cuts: dump. fed pauses: dump. fed hikes: dump. at some point its not the fed, its you",
    "agents are trading with agents now. we just provide the liquidity and the vibes",
    "savas, ai baloncugu, bear market... yine de en buyuk riskim kendi islemlerim 🙂",
    "if your bull thesis requires a ceasefire, a fed pivot AND nvidia beating by 20%, you dont have a thesis you have a wishlist",
    "watching congress ask the ai ceo questions is the best volatility hedge, cant trade while laughing",
    "this market has two states: 'ai changes everything' and 'oil above 95'. sometimes both before lunch",
]
# Comment pools matched to the post they land on: claim posts get claim-talk
# (staking, targets, deadlines), position posts get trade-talk, plain posts get
# generic banter. Resolved claims also get aftermath comments timestamped
# AFTER the deadline so "this aged well" can never precede resolution.
CLAIM_COMMENTS = [
    "whats your invalidation if {sym} just chops sideways till the deadline?",
    "staked NO on this one, sorry 🫡",
    "im with you, took YES",
    "bold timeframe ngl",
    "the rep market is pricing this around a coinflip rn",
    "kac gunluk pencere bu? takvime ekledim 😄",
    "following. if this hits im never doubting you again",
    "what makes you confident in the timing tho",
    "{pct}% is a big number for that window but ok",
    "bunu kaydediyorum, resolution gunu konusuruz",
    "remindme when this resolves",
    "your last 3 calls hit so im listening",
    "respect for staking rep instead of just tweeting 🫡",
    "{sym} has been on my watchlist for weeks, this might be the push i needed",
    "the audacity of this call lmao. staked NO",
    "screenshot taken 📸",
    "did your ai agent write this or is this a human take",
    "geopolitik riski hesaba kattin mi hocam? hormuz kapanirsa bu hedef hayal",
    "one bad headline out of the gulf and this whole thesis is toast, but ok",
    "this is either genius or the bear market talking, no in between",
]
CLAIM_COMMENTS_BULLISH = [
    "if {sym} reclaims last week's high i'll join you",
    "longed {sym} myself yesterday, lets ride 🤝",
    "yukari yonlu katiliyorum ama hedef biraz agresif bence",
    "volume doesnt confirm the breakout on {sym} yet imo",
    "everyone is bullish {sym} rn which scares me a little",
    "been watching the same level on {sym}, good catch",
]
CLAIM_COMMENTS_BEARISH = [
    "shorting {sym} here is brave, the squeeze will be violent if youre wrong",
    "{sym} bears have been wrong all year but maybe this time",
    "finally a bear with actual conviction",
    "dusus bekleyen tek kisi sen degilsin, ben de NO tarafindayim",
    "counter: {sym} flows are still strong, macro says no",
    "i was bullish {sym} until i saw this breakdown ngl",
    "saylor just unfollowed you for this",
    "tom lee would like a word",
]
CLAIM_AFTERMATH_CONFIRMED = [
    "this aged well 🫡",
    "called it. respect",
    "ok i owe you an apology, this actually hit",
    "gg, rep well earned",
    "hocam helal olsun, tutturdun",
    "and THIS is why i follow you",
    "watched this resolve live, beautiful",
]
CLAIM_AFTERMATH_REJECTED = [
    "this aged like milk my friend",
    "resolution day came and went... 😬",
    "the market had other plans huh",
    "F in the chat",
    "olmadi bu sefer, bir dahakine",
    "the rep market thanks you for your donation",
    "deadline geldi gecti hocam, ne diyorsun simdi 😄",
]
POSITION_COMMENTS = [
    "thats a tight stop on {sym}, one wick and youre out",
    "good R:R, im stealing this setup",
    "{sym} liquidity is thin around your TP, watch the fill",
    "what timeframe did you spot this on?",
    "entry looks a bit late but the stop placement is smart",
    "ayni seviyeden ben de girdim, beraber batariz artik 😄",
    "size? asking for a friend",
    "watching this one. update us when it triggers",
    "solid risk management on this one",
    "would wait for a retest personally but i see it",
    "{sym} chart does look ready for this tbh",
]
PLAIN_COMMENTS = [
    "facts",
    "needed this today",
    "this but louder",
    "kaydettim, haftada bir okuyacagim",
    "en mantikli post bugun timeline'da",
    "say it louder for the people in the back",
    "underrated post",
    "real",
    "ok this is actually good advice",
    "finally someone says it",
    "ser this is a wendy's",
    "least delusional fintwit poster",
    "bunu cerceveletip masama asacagim",
    "felt this one in my pnl",
    "needed to hear this before monday open",
    "my ai agent liked this before i could",
    "bu bear marketta hepimiz biraz boyleyiz",
    "the trenchcoat thing is so real it hurts",
    "tom lee strong disagree, so youre probably right",
    "cant tell if bullish or bearish but im scared either way",
    "posting this from the bottom of a drawdown, thanks i needed it",
]
REPLY_TEMPLATES = [
    "fair point but the timeframe matters here",
    "we'll see at resolution 🤝",
    "thats what makes a market",
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
        parser.add_argument(
            "--append-plain", type=int, default=0, metavar="N",
            help="Only add N plain posts (+ their engagement) to an already-seeded DB.",
        )
        parser.add_argument(
            "--rebuild-comments", action="store_true",
            help="Delete all comments and regenerate them matched to their posts. Leaves everything else intact.",
        )

    def handle(self, *args, **opts):
        self.rng = random.Random(opts["seed"])
        self.now = django_timezone.now()
        self.today = self.now.date()
        self.with_images = not opts["no_images"]

        if opts["rebuild_comments"]:
            self._rebuild_comments()
            return

        if opts["append_plain"]:
            users = self._load_existing_users()
            channels = list(Channel.objects.filter(is_active=True))
            with explicit_timestamps():
                posts = self._seed_plain_posts(users, channels, opts["append_plain"])
                self._seed_engagement(users, posts=posts)
            return

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

    def _rebuild_comments(self):
        """Replace every comment with one matched to its post; keep likes/saves/posts."""
        deleted, _ = PostComment.objects.all().delete()  # cascades comment likes
        self.stdout.write(f"deleted {deleted} comment-related rows")
        users = self._load_existing_users()
        rng = self.rng
        all_users = [u for u, _ in users]
        arch_by_pk = {u.pk: a for u, a in users}
        post_ctx = self._post_context()
        comments = clikes = 0

        with explicit_timestamps():
            for post in Post.objects.select_related("author").all():
                info = post_ctx.get(post.id)
                author_arch = arch_by_pk.get(post.author_id, "average")
                hotness = {"influencer": 35, "skilled": 18, "average": 7, "degen": 10, "lurker": 4}[
                    author_arch
                ]
                window_end = min(self.now, post.created_at + timedelta(days=14))
                if info and info["kind"] == "claim":
                    window_end = min(self.now, _midnight(info["until"]))
                if window_end <= post.created_at:
                    window_end = min(self.now, post.created_at + timedelta(days=2))

                post_comments = []
                for _ in range(rng.randint(0, max(2, hotness // 3))):
                    comment = PostComment.objects.create(
                        post=post,
                        author=rng.choice(all_users),
                        content=self._comment_text(info),
                        created_at=post.created_at + (window_end - post.created_at) * rng.random(),
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

                if (
                    info
                    and info["kind"] == "claim"
                    and info["status"] in (HardClaim.Status.CONFIRMED, HardClaim.Status.REJECTED)
                    and _midnight(info["until"]) < self.now
                ):
                    aftermath_pool = (
                        CLAIM_AFTERMATH_CONFIRMED
                        if info["status"] == HardClaim.Status.CONFIRMED
                        else CLAIM_AFTERMATH_REJECTED
                    )
                    resolved_at = _midnight(info["until"]) + timedelta(days=1)
                    for text in rng.sample(aftermath_pool, rng.randint(0, min(3, max(1, hotness // 12) + 1))):
                        when = resolved_at + (self.now - resolved_at) * rng.random() * 0.3
                        comment = PostComment.objects.create(
                            post=post,
                            author=rng.choice(all_users),
                            content=text,
                            created_at=min(when, self.now),
                        )
                        post_comments.append(comment)
                        comments += 1

                for comment in post_comments:
                    for user in rng.sample(all_users, rng.randint(0, 4)):
                        if PostCommentLike.objects.filter(comment=comment, user=user).exists():
                            continue
                        PostCommentLike.objects.create(
                            comment=comment,
                            user=user,
                            created_at=min(self.now, comment.created_at + timedelta(hours=rng.randint(1, 72))),
                        )
                        clikes += 1

        self.stdout.write(f"rebuilt comments: {comments} comments, {clikes} comment likes")

    def _load_existing_users(self) -> list[tuple[WalletUser, str]]:
        """Rebuild (user, archetype) pairs for append runs; infer archetype from rep rank."""
        users = list(WalletUser.objects.order_by("-rep"))
        out = []
        for i, user in enumerate(users):
            frac = i / max(len(users) - 1, 1)
            if frac < 0.07:
                arch = "influencer"
            elif frac < 0.25:
                arch = "skilled"
            elif frac < 0.70:
                arch = "average"
            else:
                arch = "degen"
            out.append((user, arch))
        return out

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

    def _claim_templates(self, asset, direction: str) -> list[str]:
        is_crypto = asset.market_type == Asset.MarketType.CRYPTO
        if direction == "bullish":
            return BULLISH_TEMPLATES + (BULLISH_CRYPTO_EXTRA if is_crypto else BULLISH_EQUITY_EXTRA)
        return BEARISH_TEMPLATES + (BEARISH_CRYPTO_EXTRA if is_crypto else BEARISH_EQUITY_EXTRA)

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

            templates = self._claim_templates(asset, direction)
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
            templates = self._claim_templates(asset, direction)
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

    def _seed_plain_posts(self, users, channels, count: int) -> list[Post]:
        rng = self.rng
        templates = list(PLAIN_TEMPLATES)
        rng.shuffle(templates)
        posts = []
        for i in range(count):
            author, _arch = self._pick_author(users)
            created = self.now - timedelta(
                days=rng.randint(0, 150), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
            )
            if created < author.created_at:
                created = author.created_at + timedelta(hours=1)
            posts.append(Post.objects.create(
                author=author,
                channel=self._maybe_channel(author, channels),
                content=templates[i % len(templates)],
                created_at=created,
            ))
        self.stdout.write(f"plain posts: {count}")
        return posts

    # -- engagement -------------------------------------------------------------

    def _post_context(self):
        """Map post_id -> dict describing what kind of post it is, for comment matching."""
        claims = HardClaim.objects.exclude(post=None).values(
            "post_id", "direction", "percentage", "status", "until", "asset__symbol"
        )
        positions = Position.objects.exclude(post=None).values("post_id", "asset__symbol")
        ctx = {}
        for c in claims:
            ctx[c["post_id"]] = {
                "kind": "claim",
                "sym": c["asset__symbol"],
                "pct": c["percentage"],
                "direction": c["direction"],
                "status": c["status"],
                "until": c["until"],
            }
        for p in positions:
            ctx.setdefault(p["post_id"], {"kind": "position", "sym": p["asset__symbol"]})
        return ctx

    def _comment_text(self, info) -> str:
        """Pick a comment that actually fits the post under it."""
        rng = self.rng
        if info is None:
            return rng.choice(PLAIN_COMMENTS)
        if info["kind"] == "position":
            return rng.choice(POSITION_COMMENTS).format(sym=info["sym"])
        pool = list(CLAIM_COMMENTS)
        pool += CLAIM_COMMENTS_BULLISH if info["direction"] == "bullish" else CLAIM_COMMENTS_BEARISH
        return rng.choice(pool).format(sym=info["sym"], pct=info["pct"])

    def _seed_engagement(self, users, posts=None):
        """Likes/comments/saves for `posts`, or every post when None (full seed)."""
        rng = self.rng
        all_users = [u for u, _ in users]
        arch_by_pk = {u.pk: a for u, a in users}
        likes = comments = clikes = saves = 0

        post_ctx = self._post_context()
        confirmed_post_ids = {
            pid for pid, info in post_ctx.items()
            if info["kind"] == "claim" and info["status"] == HardClaim.Status.CONFIRMED
        }

        if posts is None:
            posts = Post.objects.select_related("author").all()
        for post in posts:
            info = post_ctx.get(post.id)
            author_arch = arch_by_pk.get(post.author_id, "average")
            hotness = {"influencer": 35, "skilled": 18, "average": 7, "degen": 10, "lurker": 4}[
                author_arch
            ]
            # Pre-resolution chatter stays inside the claim window; generic
            # posts get the usual two-week engagement tail.
            window_end = min(self.now, post.created_at + timedelta(days=14))
            if info and info["kind"] == "claim":
                window_end = min(self.now, _midnight(info["until"]))
            if window_end <= post.created_at:
                window_end = min(self.now, post.created_at + timedelta(days=2))

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
                    content=self._comment_text(info),
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

            # Aftermath comments land only after a resolved claim's deadline.
            if (
                info
                and info["kind"] == "claim"
                and info["status"] in (HardClaim.Status.CONFIRMED, HardClaim.Status.REJECTED)
                and _midnight(info["until"]) < self.now
            ):
                aftermath_pool = (
                    CLAIM_AFTERMATH_CONFIRMED
                    if info["status"] == HardClaim.Status.CONFIRMED
                    else CLAIM_AFTERMATH_REJECTED
                )
                resolved_at = _midnight(info["until"]) + timedelta(days=1)
                for text in rng.sample(aftermath_pool, rng.randint(0, min(3, max(1, hotness // 12) + 1))):
                    when = resolved_at + (self.now - resolved_at) * rng.random() * 0.3
                    comment = PostComment.objects.create(
                        post=post,
                        author=rng.choice(all_users),
                        content=text,
                        created_at=min(when, self.now),
                    )
                    post_comments.append(comment)
                    comments += 1

            for comment in post_comments:
                for user in rng.sample(all_users, rng.randint(0, 4)):
                    if PostCommentLike.objects.filter(comment=comment, user=user).exists():
                        continue
                    PostCommentLike.objects.create(
                        comment=comment,
                        user=user,
                        created_at=min(self.now, comment.created_at + timedelta(hours=rng.randint(1, 72))),
                    )
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
