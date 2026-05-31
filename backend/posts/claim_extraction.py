"""Deterministic, RegEx / rule-based financial claim extraction.

This module is fully self-contained and has NO AI dependency. It can be used on
its own:

    from posts.claim_extraction import rule_based_claims_from_prompt
    claims = rule_based_claims_from_prompt("Bitcoin kısa vadede 103000 dolar olur.")

It also exposes the shared data model (`FinancialClaim`), the asset whitelist and
the mapping/regex helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from calendar import monthrange
from typing import Optional, List, Literal
import json
import os
import re
from difflib import get_close_matches

# ---------------------------------------------------------------------------
# 1. Whitelist & alias configuration (external JSON + embedded fallback)
# ---------------------------------------------------------------------------
# The asset whitelist (CURRENCIES / CRYPTO / STOCKS) and the natural-language
# alias map live in ``whitelist_config.json`` next to this module, so the lists
# can be maintained without touching code. If that file is missing or invalid
# we degrade gracefully to the embedded fallback below, so the module never
# fails to import.
_CONFIG_FILENAME = "whitelist_config.json"
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), _CONFIG_FILENAME)

# --- Embedded fallback (used ONLY when whitelist_config.json cannot be read) -
_FALLBACK_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "TRY", "AUD", "CAD", "NZD", "CNY"]
_FALLBACK_CRYPTO = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE", "DOT", "LINK"]
_FALLBACK_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
    "NFLX", "AMD", "INTC", "COIN", "PYPL", "PLTR", "UBER", "DIS",
]
_FALLBACK_ALIASES = {
    # Fiat currencies
    "dolar": "USD", "doları": "USD", "dolari": "USD", "amerikan doları": "USD",
    "abd doları": "USD", "us dollar": "USD", "u.s. dollar": "USD", "dollar": "USD",
    "dolr": "USD", "doller": "USD", "dolarrr": "USD",
    "avro": "EUR", "euro": "EUR", "euor": "EUR",
    "sterlin": "GBP", "ingiliz sterlini": "GBP", "pound": "GBP", "british pound": "GBP",
    "yen": "JPY", "japon yeni": "JPY",
    "frank": "CHF", "swiss franc": "CHF", "isvicre frangi": "CHF", "isviçre frangı": "CHF",
    "lira": "TRY", "turkish lira": "TRY", "turk lirasi": "TRY", "türk lirası": "TRY",
    "kanada doları": "CAD", "avustralya doları": "AUD", "yeni zelanda doları": "NZD",
    "çin yuanı": "CNY", "australian dollar": "AUD", "canadian dollar": "CAD",
    "new zealand dollar": "NZD", "yuan": "CNY", "renminbi": "CNY",
    # Crypto
    "bitcoin": "BTC", "bitcoın": "BTC", "bitcon": "BTC", "btcoin": "BTC",
    "ethereum": "ETH", "ether": "ETH", "etherium": "ETH", "etheriyum": "ETH",
    "etheryum": "ETH", "ethirium": "ETH",
    "solana": "SOL", "solona": "SOL",
    "binance coin": "BNB", "bnb coin": "BNB",
    "ripple": "XRP", "cardano": "ADA", "avalanche": "AVAX", "dogecoin": "DOGE",
    "polkadot": "DOT", "chainlink": "LINK",
    # Stocks / companies
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "nvidia": "NVDA", "tesla": "TSLA", "meta": "META",
    "netflix": "NFLX", "amd": "AMD", "intel": "INTC", "coinbase": "COIN",
    "paypal": "PYPL", "palantir": "PLTR", "uber": "UBER", "disney": "DIS",
    "walt disney": "DIS", "microsof": "MSFT", "gogle": "GOOGL", "amazn": "AMZN",
    "nvida": "NVDA", "tesl": "TSLA", "netfliix": "NFLX",
}


def _load_whitelist_config(path: str = _CONFIG_PATH):
    """Load (currencies, crypto, stocks, aliases) from JSON or embedded fallback.

    Never raises: any IO / parse / shape error degrades gracefully to the
    embedded defaults so importing this module can never crash the app.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        currencies = [str(s).strip().upper() for s in data.get("currencies", []) if str(s).strip()]
        crypto = [str(s).strip().upper() for s in data.get("crypto", []) if str(s).strip()]
        stocks = [str(s).strip().upper() for s in data.get("stocks", []) if str(s).strip()]
        aliases = {
            str(k).strip().lower(): str(v).strip().upper()
            for k, v in dict(data.get("aliases", {})).items()
            if str(k).strip() and str(v).strip()
        }
        if not (currencies or crypto or stocks):
            raise ValueError("whitelist_config.json defines no assets")
        return currencies, crypto, stocks, aliases
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return (
            list(_FALLBACK_CURRENCIES),
            list(_FALLBACK_CRYPTO),
            list(_FALLBACK_STOCKS),
            dict(_FALLBACK_ALIASES),
        )


# Active whitelist groups + alias map, mapped into memory once at import time.
CURRENCIES, CRYPTO, STOCKS, alias_map = _load_whitelist_config()

# Global kontrol listesi (numerator/denominator validation set).
TOTAL_WHITELIST = CURRENCIES + CRYPTO + STOCKS

# Lower-cased ticker lookup ("btc" -> "BTC"), rebuilt from the active whitelist.
ticker_map = {ticker.lower(): ticker for ticker in TOTAL_WHITELIST}


# ---------------------------------------------------------------------------
# 3. Veri Yapısı (shared model)
# ---------------------------------------------------------------------------
@dataclass
class FinancialClaim:
    pay: Optional[str]            # Numerator. Whitelist ticker symbol (e.g. BTC).
    value: Optional[float]        # Pure numeric magnitude.
    value_type: Literal["PRICE", "PERCENTAGE_UP", "PERCENTAGE_DOWN"] = "PRICE"
    payda: Optional[str] = None   # Denominator. Only when present on the whitelist.
    deadline: Optional[str] = None  # ISO formatted date.
    status: str = "INCOMPLETE_CLAIM"  # 'HARD_CLAIM' or 'INCOMPLETE_CLAIM'.

    def __post_init__(self):
        # pay must resolve to a whitelist ticker (mirrors the previous validator).
        if self.pay not in TOTAL_WHITELIST:
            raise ValueError(f"Geçersiz Pay: {self.pay}")
        # A denominator outside the whitelist is dropped rather than rejected.
        if self.payda is not None and self.payda not in TOTAL_WHITELIST:
            self.payda = None

    def to_dict(self) -> dict:
        if self.value is None:
            value_str = "?"
        elif self.value_type == "PERCENTAGE_UP":
            value_str = f"+{self.value}%"
        elif self.value_type == "PERCENTAGE_DOWN":
            value_str = f"-{self.value}%"
        else:
            value_str = str(self.value)

        pay_str = self.pay if self.pay else "Unknown Asset"

        parts = [pay_str, "→", value_str]
        if self.payda:
            parts.append(self.payda)
        if self.deadline:
            parts += ["by", self.deadline]

        return {
            "pay": self.pay,
            "payda": self.payda,
            "value": self.value,
            "value_type": self.value_type,
            "deadline": self.deadline,
            "status": self.status,
            "text": " ".join(parts),
        }


# ---------------------------------------------------------------------------
# Deadline extraction
# ---------------------------------------------------------------------------
def _lower_text(text: str) -> str:
    """Lowercase TR/EN text; normalise Turkish ``İ`` so ``İlk`` → ``ilk``."""
    return text.replace("İ", "i").lower()


def extract_year_end_deadline(text: str) -> Optional[str]:
    """If text contains year-end expression, return YYYY-12-31."""
    lowered = _lower_text(text)
    patterns = [
        r"(20\d{2})\D{0,25}(yıl sonu|yıl sonunda|yıl sonuna kadar|sene sonu|sene sonunda|sonunda|end of year|year[- ]end|by year[- ]end)",
        r"(yıl sonu|yıl sonunda|yıl sonuna kadar|sene sonu|sene sonunda|end of year|year[- ]end|by year[- ]end)\D{0,25}(20\d{2})",
        r"(end of)\D{0,10}(20\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        year = next((group for group in match.groups() if group and group.isdigit()), None)
        if year:
            return f"{year}-12-31"
    return None


def extract_relative_deadline(text: str, base_date: Optional[datetime] = None) -> Optional[str]:
    """Convert short/medium/long term phrases to absolute ISO date.

    ``base_date`` lets callers inject a fixed reference instant (e.g. when
    re-processing an old tweet or in tests); it defaults to ``datetime.now()``.
    """
    now = base_date if base_date is not None else datetime.now()
    lowered = _lower_text(text)
    if re.search(r"\b(kısa\s+vade(li|de)?|short(\s|-)?term)\b", lowered):
        return (now + timedelta(days=30)).strftime("%Y-%m-%d")
    if re.search(r"\b(orta\s+vade(li|de)?|medium(\s|-)?term|mid(\s|-)?term)\b", lowered):
        return (now + timedelta(days=365)).strftime("%Y-%m-%d")
    if re.search(r"\b(uzun\s+vade(li|de)?|long(\s|-)?term)\b", lowered):
        return (now + timedelta(days=1000)).strftime("%Y-%m-%d")
    return None


# ---------------------------------------------------------------------------
# Deadline helpers (TR + EN month names, quarter / half resolvers)
# ---------------------------------------------------------------------------
_EN_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_TR_MONTHS = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5,
    "mayis": 5, "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8,
    "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11, "kasim": 11,
    "aralık": 12, "aralik": 12,
}
_ALL_MONTHS = {**_EN_MONTHS, **_TR_MONTHS}
# Longest names first so "march" wins over "mar", "june" over "jun", etc.
_MONTH_ALT = "|".join(sorted((re.escape(k) for k in _ALL_MONTHS), key=len, reverse=True))

_QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


def _last_day_of_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def _iso(year: int, month: int, day: Optional[int] = None, base_date: Optional[datetime] = None) -> str:
    """Build an ISO date; default day = last day of the month.

    ``base_date`` is accepted for signature symmetry with the other date
    helpers (so callers can pass it uniformly). The result depends only on the
    explicit year/month/day, so the parameter does not alter the output.
    """
    if day is None:
        day = _last_day_of_month(year, month)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _year_in_text(lowered: str, base_date: Optional[datetime] = None) -> int:
    """Use an explicit 20xx year if present, otherwise the reference year."""
    now = base_date if base_date is not None else datetime.now()
    m = re.search(r"\b(20\d{2})\b", lowered)
    return int(m.group(1)) if m else now.year


def _detect_quarter(lowered: str) -> Optional[int]:
    """Detect a financial quarter (Q1..Q4, '1. çeyrek', 'first quarter', 'Ç1').

    Turkish suffixes are tolerated ('çeyrekte', 'çeyreğinde') by not requiring a
    trailing word boundary on the Turkish stem.
    """
    m = re.search(r"\bq\s{0,500}([1-4])\b", lowered) or re.search(r"\bç\s{0,500}([1-4])\b", lowered)
    if m:
        return int(m.group(1))
    m = re.search(r"\b([1-4])\s{0,500}\.?\s{0,500}(?:çeyre|quarter)", lowered)
    if m:
        return int(m.group(1))
    ordinals = [
        (r"\b(?:ilk çeyre|first quarter|1st quarter)", 1),
        (r"\b(?:ikinci çeyre|second quarter|2nd quarter)", 2),
        (r"\b(?:üçüncü çeyre|uçuncu çeyre|third quarter|3rd quarter)", 3),
        (r"\b(?:dördüncü çeyre|dorduncu çeyre|fourth quarter|4th quarter)", 4),
    ]
    for pattern, q in ordinals:
        if re.search(pattern, lowered):
            return q
    return None


def _detect_half(lowered: str) -> Optional[int]:
    """Detect a financial half-year (H1/H2, '1H/2H', 'ilk yarı', 'first half').

    Turkish suffixes ('yarıda', 'yarısında') are tolerated.
    """
    if re.search(r"\b(?:h1|1h)\b", lowered) or re.search(
        r"\b(?:ilk yar[ıi]|yılın ilk yar[ıi]|first half|1st half)", lowered
    ):
        return 1
    if re.search(r"\b(?:h2|2h)\b", lowered) or re.search(
        r"\b(?:ikinci yar[ıi]|yılın ikinci yar[ıi]|second half|2nd half)", lowered
    ):
        return 2
    return None


def _detect_month_period(lowered: str, base_date: Optional[datetime] = None) -> Optional[str]:
    """Resolve a month name carrying an end / mid / beginning cue.

    "End of August" -> last day of Aug, "Mid-July" -> the 15th,
    "Ocak sonu" -> last day of Jan, "Mart ortası" -> Mar 15,
    "Ekim ayı içinde" -> last day of Oct. A bare month with no cue is ignored
    to avoid false positives (e.g. the modal verb "may"). ``base_date`` feeds
    the implicit-year resolution.
    """
    for mname, month in _ALL_MONTHS.items():
        m = re.search(rf"\b{re.escape(mname)}\b", lowered)
        if not m:
            continue
        year = _year_in_text(lowered, base_date)
        window = lowered[max(0, m.start() - 14): m.end() + 16]
        if re.search(r"\bmid|ortas", window):
            return _iso(year, month, 15, base_date)
        if re.search(r"end of|sonu|içinde|by end", window):
            return _iso(year, month, base_date=base_date)
        if re.search(r"\bbaş|early|beginning|start of", window):
            return _iso(year, month, 1, base_date)
    return None


def extract_deadline(text: str, base_date: Optional[datetime] = None) -> Optional[str]:
    """Extract an absolute ISO deadline (YYYY-MM-DD) from TR/EN expressions.

    ``base_date`` injects a fixed reference instant so relative expressions
    ("yarın", "next week", "kısa vade") resolve against it instead of the
    wall clock. Defaults to ``datetime.now()``.
    """
    now = base_date if base_date is not None else datetime.now()
    lowered = _lower_text(text)

    # 1) Explicit numeric dates -------------------------------------------
    iso = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", text)
    if iso:
        y, mo, d = int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return _iso(y, mo, d)
    dmy = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b", text)
    if dmy:
        d, mo, y = int(dmy.group(1)), int(dmy.group(2)), int(dmy.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return _iso(y, mo, d)

    # 2) Month-name + day ("June 15", "15th of June 2026", "15 Haziran 2026")
    md = re.search(
        rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?!\s{{0,500}}%)(?:,?\s{{0,500}}(20\d{{2}}))?",
        lowered,
    )
    if md:
        month, day = _ALL_MONTHS[md.group(1)], int(md.group(2))
        year = int(md.group(3)) if md.group(3) else _year_in_text(lowered, base_date)
        if 1 <= day <= _last_day_of_month(year, month):
            return _iso(year, month, day)
    dm = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_ALT})\b(?:,?\s{{0,500}}(20\d{{2}}))?",
        lowered,
    )
    if dm:
        day, month = int(dm.group(1)), _ALL_MONTHS[dm.group(2)]
        year = int(dm.group(3)) if dm.group(3) else _year_in_text(lowered, base_date)
        if 1 <= day <= _last_day_of_month(year, month):
            return _iso(year, month, day)

    # 3) Quarters ----------------------------------------------------------
    quarter = _detect_quarter(lowered)
    if quarter:
        mo, d = _QUARTER_END[quarter]
        return _iso(_year_in_text(lowered, base_date), mo, d)

    # 4) Halves ------------------------------------------------------------
    half = _detect_half(lowered)
    if half == 1:
        return _iso(_year_in_text(lowered, base_date), 6, 30)
    if half == 2:
        return _iso(_year_in_text(lowered, base_date), 12, 31)

    # 5) Year-end / EOY ----------------------------------------------------
    if re.search(r"\beoy\b", lowered) or re.search(
        r"yıl sonu|yil sonu|yıl sonunda|sene sonu|sene sonunda|yıl sonuna kadar|"
        r"yıl sonu itibarıyla|end of (?:the )?year|year[- ]end|by year[- ]end",
        lowered,
    ):
        return f"{_year_in_text(lowered, base_date)}-12-31"

    # 6) Month with end / mid / beginning cue ("End of August", "Mart ortası")
    month_dl = _detect_month_period(lowered, base_date)
    if month_dl:
        return month_dl

    # 7) End of month / EOM ------------------------------------------------
    if re.search(r"\beom\b|ay sonu|ay sonunda|month[- ]end|end of (?:the )?month", lowered):
        return _iso(now.year, now.month)

    # 8) Today / tomorrow --------------------------------------------------
    # Turkish stems take a trailing \w* so inflected forms also match:
    # "bugüne", "yarına", "yarından".
    if re.search(r"\b(?:bugün|bugun)\w{0,500}|\btoday\b", lowered):
        return now.strftime("%Y-%m-%d")
    if re.search(r"\b(?:yarın|yarin)\w{0,500}|\btomorrow\b", lowered):
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    # 9) Numeric durations ("in 2 weeks", "3 gün içinde", "within 5 days") --
    #    Checked BEFORE the bare relative week/month so "2 hafta" stays +14
    #    days instead of collapsing onto the inflection-tolerant "hafta\\w*".
    wk = re.search(r"(\d{1,500})\s{0,500}(?:hafta|week|weeks)\b", lowered)
    if wk:
        return (now + timedelta(weeks=int(wk.group(1)))).strftime("%Y-%m-%d")
    dy = re.search(r"(\d{1,500})\s{0,500}(?:gün|gun|day|days)\b", lowered)
    if dy:
        return (now + timedelta(days=int(dy.group(1)))).strftime("%Y-%m-%d")
    mo_ = re.search(r"(\d{1,500})\s{0,500}(?:ay|month|months)\b", lowered)
    if mo_:
        return (now + timedelta(days=int(mo_.group(1)) * 30)).strftime("%Y-%m-%d")
    yr = re.search(r"(\d{1,500})\s{0,500}(?:yıl|yil|year|years)\b", lowered)
    if yr:
        return (now + timedelta(days=int(yr.group(1)) * 365)).strftime("%Y-%m-%d")

    # 10) Relative week / month (inflection-tolerant) ----------------------
    # "haftaya", "haftayı", "gelecek hafta", "önümüzdeki ayında" all match.
    if re.search(
        r"\b(?:hafta\w{0,500}|gelecek hafta|önümüzdeki hafta|onumuzdeki hafta)\b|\bnext week\b",
        lowered,
    ):
        return (now + timedelta(days=7)).strftime("%Y-%m-%d")
    if re.search(
        r"\b(?:gelecek|önümüzdeki|onumuzdeki)\s+ay\w{0,500}|\bnext month\b",
        lowered,
    ):
        return (now + timedelta(days=30)).strftime("%Y-%m-%d")
    if re.search(
        r"\b(?:gelecek|önümüzdeki|onumuzdeki|ertesi)\s+yıl\w{0,500}|\bnext year\b",
        lowered,
    ):
        return (now + timedelta(days=365)).strftime("%Y-%m-%d")

    # 11) Short / medium / long term ---------------------------------------
    relative = extract_relative_deadline(text, base_date)
    if relative:
        return relative

    # 12) Verbal year with period cue ("2027 başında", "2028 sonu") --------
    verbal = re.search(r"\b(20\d{2})\s{0,500}(baş\w{0,500}|son\w{0,500}|yıl\w{0,500}|için\w{0,500}|icin\w{0,500})", lowered)
    if verbal:
        year = verbal.group(1)
        suffix = (verbal.group(2) or "").lower()
        if suffix.startswith("baş") or suffix.startswith("bas"):
            return f"{year}-01-01"
        return f"{year}-12-31"

    # 13) Explicit year with a generic period cue ----------------------------
    explicit_year = re.search(r"\b(20\d{2})\b", lowered)
    if explicit_year and re.search(r"başında|sonunda|yıl|end|year", lowered):
        return f"{explicit_year.group(1)}-12-31"
    return None


# ---------------------------------------------------------------------------
# Turkish inflection handling (case + possessive suffixes / iyelik & hâl ekleri)
# ---------------------------------------------------------------------------
# Common Turkish noun suffixes with vowel-harmony and buffer-consonant (y/n/s)
# variants. Used to recover an asset's dictionary stem from an inflected mention
# such as "lirayı" -> "lira", "dolardan" -> "dolar", "euroya" -> "euro",
# "bitcoini" -> "bitcoin", "ethereum'u" -> "ethereum". Matching tries every
# candidate stem and keeps whichever maps onto a whitelist asset, so list order
# is for readability only.
_TR_NOUN_SUFFIXES = (
    # plural (optionally followed by case / possessive)
    "larını", "lerini", "larına", "lerine", "larında", "lerinde",
    "larından", "lerinden", "larımız", "lerimiz", "larınız", "leriniz",
    "ları", "leri", "ların", "lerin", "lara", "lere", "larda", "lerde",
    "lardan", "lerden", "lar", "ler",
    # possessive (+ case)
    "ımız", "imiz", "umuz", "ümüz", "ınız", "iniz", "unuz", "ünüz",
    "sının", "sinin", "sunun", "sünün", "ımı", "imi", "umu", "ümü",
    "sını", "sini", "sunu", "sünü", "sı", "si", "su", "sü",
    "ım", "im", "um", "üm",
    # genitive
    "nın", "nin", "nun", "nün", "ın", "in", "un", "ün",
    # ablative / locative (+ buffer n)
    "ndan", "nden", "dan", "den", "tan", "ten", "nda", "nde",
    "da", "de", "ta", "te",
    # dative (+ buffer y / n)
    "yna", "yne", "na", "ne", "ya", "ye", "a", "e",
    # accusative (+ buffer y / n)
    "yı", "yi", "yu", "yü", "nı", "ni", "nu", "nü", "ı", "i", "u", "ü",
    # instrumental / "ile"
    "yla", "yle", "la", "le",
)


def _turkish_noun_stems(word: str) -> List[str]:
    """Candidate dictionary stems after stripping Turkish noun suffixes.

    Only stems with at least 3 letters are kept, so a word is never collapsed to
    a 1-2 letter fragment that would fuzzy-match almost anything.
    """
    stems: List[str] = []
    seen: set = set()
    for suffix in _TR_NOUN_SUFFIXES:
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            if len(stem) >= 3 and stem not in seen:
                seen.add(stem)
                stems.append(stem)
    return stems


# ---------------------------------------------------------------------------
# Asset mapping
# ---------------------------------------------------------------------------
def map_asset_token(token: str, allow_multi_token: bool = True, allow_fuzzy: bool = True) -> Optional[str]:
    """Map natural-language asset names/synonyms to whitelist tickers.

    When ``allow_multi_token`` is False the lenient "scan each word" fallback is
    skipped, so a phrase only matches if it maps *as a whole*. When
    ``allow_fuzzy`` is False the typo-correction step is skipped. Both are
    disabled (per word-count) by the positional mention scanner so that a
    multi-word span like "k dolar" cannot fuzzy-collapse into a single mention
    that overlaps a number ("BTC 100k dolar").
    """
    stripped = token.strip()
    normalized = re.sub(r"[^a-zA-ZÇĞİÖŞÜçğıöşü\s]", "", stripped.lower())

    # A bare ticker SYMBOL is only accepted when the source token is written in
    # uppercase (e.g. "USD", "BTC", "COIN", "TRY"). This is critical because several
    # tickers are spelled like ordinary words once lower-cased — COIN/"coin",
    # LINK/"link", DOT/"dot", META/"meta", TRY/"try" — and must NOT be captured from
    # plain prose. Full names / synonyms ("bitcoin", "dolar") are matched separately
    # via alias_map and stay case-insensitive.
    is_symbol_style = stripped.isupper()

    # ``ticker_map`` and ``alias_map`` are module-level structures built once from
    # whitelist_config.json (see _load_whitelist_config); they are not rebuilt on
    # each call, which keeps the whitelist a single source of truth.

    # 1) Natural-language alias / full name (case-insensitive, always allowed).
    if alias_map.get(normalized) in TOTAL_WHITELIST:
        return alias_map[normalized]

    # 2) Bare ticker symbol — only when written in uppercase in the source text.
    if is_symbol_style and ticker_map.get(normalized) in TOTAL_WHITELIST:
        return ticker_map[normalized]

    # 3) Fuzzy fallback for human typos — restricted to alias/name keys only.
    #    (Fuzzy-matching short ticker symbols is unsafe: "try"->TRY, "dot"->DOT, etc.)
    if allow_fuzzy:
        close = get_close_matches(normalized, list(alias_map.keys()), n=1, cutoff=0.82)
        if close and alias_map.get(close[0]) in TOTAL_WHITELIST:
            return alias_map[close[0]]

    # 3.5) Turkish inflected full name / alias ("lirayı"->TRY, "dolardan"->USD,
    #      "euroya"->EUR, "bitcoini"->BTC). Strip noun suffixes, then re-check the
    #      alias table (exact first, then a tight fuzzy pass for typos).
    for stem in _turkish_noun_stems(normalized):
        if alias_map.get(stem) in TOTAL_WHITELIST:
            return alias_map[stem]
        if allow_fuzzy:
            close = get_close_matches(stem, list(alias_map.keys()), n=1, cutoff=0.88)
            if close and alias_map.get(close[0]) in TOTAL_WHITELIST:
                return alias_map[close[0]]

    # 4) Multi-token fallback: check each word independently (e.g., "ether fiyatı").
    #    Symbols still require uppercase; names are matched via alias_map.
    if not allow_multi_token:
        return None
    raw_parts = stripped.split()
    for raw_part in raw_parts:
        part_norm = re.sub(r"[^a-zA-ZÇĞİÖŞÜçğıöşü]", "", raw_part.lower())
        if alias_map.get(part_norm) in TOTAL_WHITELIST:
            return alias_map[part_norm]
        if raw_part.isupper() and ticker_map.get(part_norm) in TOTAL_WHITELIST:
            return ticker_map[part_norm]
        for stem in _turkish_noun_stems(part_norm):
            if alias_map.get(stem) in TOTAL_WHITELIST:
                return alias_map[stem]
    return None


# ---------------------------------------------------------------------------
# Value / asset extraction helpers
# ---------------------------------------------------------------------------
def _extract_pair_assets(text: str) -> tuple[Optional[str], Optional[str]]:
    pair = re.search(r"([A-Za-zÇĞİÖŞÜçğıöşü]{2,20})\s{0,500}/\s{0,500}([A-Za-zÇĞİÖŞÜçğıöşü]{2,20})", text)
    if not pair:
        return None, None
    pay = map_asset_token(pair.group(1))
    payda = map_asset_token(pair.group(2))
    return pay, payda


# ---------------------------------------------------------------------------
# Financial number parsing (multipliers, compound numbers, separators)
# ---------------------------------------------------------------------------
# Letter multipliers attached to / following a number (English market jargon).
_LETTER_MULTIPLIERS = {"k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}
# Word multipliers (Turkish + English).
_WORD_MULTIPLIERS = {
    "bin": 1_000.0, "thousand": 1_000.0,
    "milyon": 1_000_000.0, "million": 1_000_000.0,
    "milyar": 1_000_000_000.0, "billion": 1_000_000_000.0,
}
_ALL_MULTIPLIERS = {**_WORD_MULTIPLIERS, **_LETTER_MULTIPLIERS}
# Word multipliers first so "million" wins over the single letter "m".
_MULT_ALT = "|".join(sorted(_ALL_MULTIPLIERS, key=len, reverse=True))
# A numeric token starts and ends with a digit; it may carry "." / "," inside
# and an optional (attached or space-separated) multiplier.
_NUMBER_TOKEN_RE = re.compile(
    rf"(?P<num>\d[\d.,]*\d|\d)\s{{0,500}}(?P<mult>{_MULT_ALT})?\b",
    re.IGNORECASE,
)


def _looks_like_date_token(token: str) -> bool:
    """dd.mm.yyyy / yyyy.mm.dd style tokens must not be read as a value."""
    return bool(
        re.fullmatch(r"\d{1,2}[.,]\d{1,2}[.,]\d{2,4}", token)
        or re.fullmatch(r"\d{4}[.,]\d{1,2}[.,]\d{1,2}", token)
    )


def _normalize_number_string(raw: str) -> Optional[float]:
    """Resolve thousand / decimal separators into a float.

    Rules:
      - "103.000" / "1.500.000" (groups of 3) -> thousands separators -> 103000.0
      - "49.10" / "49,10" (1-2 trailing digits) -> decimal -> 49.10
      - mixed "1.200.000,50" / "1,200,000.50" -> the last separator is decimal
    """
    s = raw.strip()
    if not s or not re.fullmatch(r"\d[\d.,]*\d|\d", s):
        return None

    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:  # mixed -> last separator is the decimal point
        last_sep = max(s.rfind("."), s.rfind(","))
        int_part = re.sub(r"[.,]", "", s[:last_sep])
        frac_part = s[last_sep + 1:]
        try:
            return float(f"{int_part}.{frac_part}")
        except ValueError:
            return None

    sep = "." if has_dot else ("," if has_comma else None)
    if sep is None:
        try:
            return float(s)
        except ValueError:
            return None

    parts = s.split(sep)
    if len(parts) > 2:  # several separators -> all thousands groupings
        try:
            return float("".join(parts))
        except ValueError:
            return None

    left, right = parts
    if len(right) == 3:  # exactly 3 trailing digits -> thousands separator
        try:
            return float(left + right)
        except ValueError:
            return None
    try:  # otherwise decimal
        return float(f"{left}.{right}")
    except ValueError:
        return None


def _multiplier_factor(mult: Optional[str]) -> Optional[float]:
    if not mult:
        return None
    return _ALL_MULTIPLIERS.get(mult.lower())


def _token_base_value(m: "re.Match") -> Optional[float]:
    """Number * multiplier for a single matched token."""
    num = _normalize_number_string(m.group("num"))
    if num is None:
        return None
    factor = _multiplier_factor(m.group("mult"))
    return num * (factor if factor is not None else 1.0)


def _scan_number_groups(text: str) -> List[tuple]:
    """Scan text into (value, start, end) groups.

    Consecutive multiplier tokens of strictly descending magnitude are merged
    via cumulative addition:
      "3 milyon 500 bin"       -> 3_500_000.0
      "1 billion 200 million"  -> 1_200_000_000.0
    """
    matches = [
        m for m in _NUMBER_TOKEN_RE.finditer(text)
        if not _looks_like_date_token(m.group("num"))
    ]
    groups: List[tuple] = []
    i = 0
    while i < len(matches):
        m = matches[i]
        base = _token_base_value(m)
        if base is None:
            i += 1
            continue
        total = base
        end = m.end()
        last_factor = _multiplier_factor(m.group("mult"))
        j = i + 1
        while j < len(matches) and last_factor is not None:
            nxt = matches[j]
            gap = text[matches[j - 1].end(): nxt.start("num")]
            nxt_factor = _multiplier_factor(nxt.group("mult"))
            nxt_val = _token_base_value(nxt)
            if (
                nxt_val is not None
                and nxt_factor is not None
                and nxt_factor < last_factor
                and re.fullmatch(r"\s{0,500}", gap)
            ):
                total += nxt_val
                end = nxt.end()
                last_factor = nxt_factor
                j += 1
            else:
                break
        groups.append((total, m.start("num"), end))
        i = j if j > i + 1 else i + 1
    return groups


def _in_period_context(text: str, start: int, end: int) -> bool:
    """True when a number is part of a quarter / half marker (Q3, Ç1, 1H, 2H).

    Prevents the '3' in 'Q3' or the '1' in '1H' from being read as a value.
    The 'h' prefix must be directly attached (so tickers ending in H like
    'ETH 3000' are NOT mistaken for a half-year marker).
    """
    before = text[max(0, start - 2):start].lower()
    after = text[end:end + 8].lower()
    if re.search(r"(?:[qç]\s{0,500}|h)$", before):
        return True
    if re.match(r"\s{0,500}(?:h\b|\.?\s{0,500}çeyre|\.?\s{0,500}quarter|\.?\s{0,500}yar[ıi]|\.?\s{0,500}half)", after):
        return True
    return False


def _number_is_percentage(text: str, start: int, end: int) -> bool:
    """True when a number is a percentage magnitude (role #1 in the hierarchy).

    A number counts as a percentage when a '%' sign sits immediately on either
    side, or when it is introduced by "yüzde" / "percent" (any inflection:
    "yüzdesi", "percentage") just before it. Such numbers are NOT price targets
    and must be kept out of the price pool used by PRICE claims.
    """
    before = text[max(0, start - 10):start].lower()
    after = text[end:end + 10].lower()
    if re.search(r"%\s{0,500}$", before) or re.search(r"(?:y[uü]zde|percent)\w{0,500}\s{0,500}$", before):
        return True
    if re.match(r"\s{0,500}%|\s{0,500}percent", after):
        return True
    return False


def parse_financial_number(text: str) -> Optional[float]:
    """Parse the most relevant financial number from a piece of text.

    Handles letter multipliers ("100k" -> 100000.0, "1.5M" -> 1500000.0),
    word multipliers ("500 bin" -> 500000.0, "2.5 million" -> 2500000.0),
    compound / cumulative numbers ("3 milyon 500 bin" -> 3500000.0) and
    thousand-vs-decimal separator ambiguity ("103.000" -> 103000.0,
    "49.10" -> 49.10). Returns None when no number is present.
    """
    groups = _scan_number_groups(text)
    if not groups:
        return None
    return groups[-1][0]


def _extract_last_value(text: str) -> tuple[Optional[float], int]:
    groups = _scan_number_groups(text)
    if not groups:
        return None, -1
    value, _start, end = groups[-1]
    return value, end


def _extract_value_with_payda(
    text: str, deadlines: Optional[List[dict]] = None
) -> tuple[Optional[float], Optional[str], int]:
    """Extract target value and the asset/currency token following it.

    Numbers already consumed by a deadline span ("2 hafta") or a percentage
    marker ("%5") are skipped — a price target can only come from a number left
    unassigned by the higher-priority roles.
    """
    candidates: list[tuple[float, Optional[str], int]] = []
    for value, start, end in _scan_number_groups(text):
        if _in_period_context(text, start, end):
            continue
        if deadlines and _number_inside_deadline(start, end, deadlines):
            continue
        if _number_is_percentage(text, start, end):
            continue
        token_match = re.match(r"\s{0,500}([A-Za-zÇĞİÖŞÜçğıöşü$€₺]{2,15})", text[end:])
        if not token_match:
            continue
        unit = map_asset_token(token_match.group(1))
        candidates.append((value, unit, end))
    if not candidates:
        return None, None, -1
    return candidates[-1]


def _extract_best_numeric_value(
    text: str, deadlines: Optional[List[dict]] = None
) -> tuple[Optional[float], int]:
    """Extract likely target value, honouring the number-role hierarchy.

    HARD exclusions (a number can NEVER be a price): period markers (Q3/1H),
    deadline-consumed numbers ("2 hafta") and percentage magnitudes ("%5"). If
    nothing survives them, there is no price candidate and ``(None, -1)`` is
    returned so the caller can treat the claim as incomplete. A SOFT year/time
    heuristic then merely *prefers* a non-year number among the survivors.
    """
    lowered = text.lower()
    groups = _scan_number_groups(text)
    if not groups:
        return None, -1

    # HARD pool: numbers not claimed by a higher-priority role.
    allowed: list[tuple] = [
        (value, start, end)
        for value, start, end in groups
        if not _in_period_context(text, start, end)
        and not (deadlines and _number_inside_deadline(start, end, deadlines))
        and not _number_is_percentage(text, start, end)
    ]
    if not allowed:
        return None, -1

    time_units = {
        "gün", "gun", "day", "days", "ay", "month", "months",
        "yıl", "yil", "year", "years", "hafta", "week", "weeks",
    }
    has_year_ctx = bool(re.search(r"end|year|yıl|sonu|baş", lowered))
    soft: list[tuple] = []
    for value, start, end in allowed:
        tail = lowered[end: end + 15]
        if any(unit in tail for unit in time_units):
            continue
        if 1900 <= value <= 2100 and has_year_ctx:
            continue
        soft.append((value, start, end))

    chosen = soft[-1] if soft else allowed[-1]
    return chosen[0], chosen[2]


def _extract_percentage_value(text: str) -> tuple[Optional[float], int]:
    """Extract percentage amount from patterns like %10, 10%, yüzde 10."""
    percent_patterns = [
        r"%\s{0,500}(\d{1,500}(?:[.,]\d{1,500})?)",
        r"(\d{1,500}(?:[.,]\d{1,500})?)\s{0,500}%",
        r"y[uü]zde\s{0,500}(\d{1,500}(?:[.,]\d{1,500})?)",
        r"(\d{1,500}(?:[.,]\d{1,500})?)\s{0,500}percent",
    ]
    lowered = text.lower()
    for pattern in percent_patterns:
        m = re.search(pattern, lowered, flags=re.IGNORECASE)
        if not m:
            continue
        try:
            return float(m.group(1).replace(",", ".")), m.end()
        except ValueError:
            continue
    return None, -1


def _detect_value_type(text: str, raw_value_type: Optional[str] = None) -> str:
    """Infer value type from explicit raw type or language cues."""
    if raw_value_type in {"PRICE", "PERCENTAGE_UP", "PERCENTAGE_DOWN"}:
        return raw_value_type

    lowered = text.lower()
    up_keywords = [
        "artış", "artis", "yükselecek", "yukselecek", "değer kazanacak", "deger kazanacak",
        "increase", "rise", "up", "gain", "higher",
    ]
    down_keywords = [
        "azalış", "azalis", "düşecek", "dusecek", "değer kaybedecek", "deger kaybedecek",
        "decrease", "drop", "fall", "down", "lower",
    ]
    has_percent = "%" in lowered or "yüzde" in lowered or "yuzde" in lowered or "percent" in lowered
    if has_percent or any(k in lowered for k in up_keywords + down_keywords):
        if any(k in lowered for k in down_keywords):
            return "PERCENTAGE_DOWN"
        return "PERCENTAGE_UP"
    return "PRICE"


def _extract_base_payda_from_text(text: str) -> Optional[str]:
    """Extract explicit denominator/base clues for percentage claims."""
    lowered = text.lower()
    base_patterns = [
        r"([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})\s+baz[ıi]nda",
        r"([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})\s+kar[sş][ıi]s[ıi]nda",
        r"against\s+([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})",
        r"versus\s+([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})",
        r"vs\.?\s{0,500}([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})",
    ]
    for pattern in base_patterns:
        m = re.search(pattern, lowered, flags=re.IGNORECASE)
        if not m:
            continue
        mapped = map_asset_token(m.group(1))
        if mapped:
            return mapped
    return None


def _extract_primary_asset(text: str) -> Optional[str]:
    tokens = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", text)
    # Prefer the longest n-gram first so multi-word names ("binance coin",
    # "us dollar") match before a single token inside them ("coin" -> COIN).
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i:i + n])
            mapped = map_asset_token(phrase)
            if mapped:
                return mapped
    return None


def _extract_payda_near_value(text: str, value_end: int, pay: Optional[str]) -> Optional[str]:
    tail = text[value_end:] if value_end >= 0 else text
    for token in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", tail):
        mapped = map_asset_token(token)
        if mapped and mapped != pay:
            return mapped
    for token in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", text):
        mapped = map_asset_token(token)
        if mapped and mapped != pay:
            return mapped
    return None


# ---------------------------------------------------------------------------
# Pre-filter helpers (shared gate, reused by the AI layer)
# ---------------------------------------------------------------------------
def has_asset_signal(text: str) -> bool:
    """Lenient check: does the text reference any whitelist asset at all?

    Accepts a currency symbol ($/€/₺), an X/Y pair, or any name/ticker that
    map_asset_token recognizes (full names like 'bitcoin'/'dolar' plus
    uppercase symbols like 'BTC'/'USD'). Used only as a pre-AI gate, so it errs
    toward 'yes' — final precision is still enforced downstream.
    """
    if re.search(r"[$€₺]", text):
        return True
    pay, payda = _extract_pair_assets(text)
    if pay or payda:
        return True
    return _extract_primary_asset(text) is not None


def passes_prefilter(prompt: str) -> bool:
    """Deterministic gate run BEFORE any AI call.

    Passes when the text can plausibly yield a claim under the Anchor Rule:
    a whitelist asset plus (a number OR a time expression). Asset-only prose
    with no value cue and no deadline is rejected.
    """
    if not prompt or not prompt.strip():
        return False
    if not has_asset_signal(prompt):
        return False
    if re.search(r"\d", prompt):
        return True
    # No digit — still OK if a deadline / time phrase is present ("Dolar haftaya").
    return bool(_scan_deadline_mentions(prompt)) or extract_deadline(prompt) is not None


# ---------------------------------------------------------------------------
# Ensemble extraction (multi-strategy + scoring)
# ---------------------------------------------------------------------------
_SYMBOL_ASSETS = {"$": "USD", "€": "EUR", "₺": "TRY"}

# Clause boundaries: sentence punctuation + Turkish conjunctions. A comma / dot
# sitting *between digits* is NOT a split point (it is a number separator, e.g.
# "103.000" or "49,10").
_CLAUSE_SPLIT_RE = re.compile(
    r"(?<!\d)[.,](?!\d)|;|\b(?:ve|veya|fakat|ama|ancak)\b",
    re.IGNORECASE,
)


def _is_percentage_type(value_type: str) -> bool:
    return value_type in {"PERCENTAGE_UP", "PERCENTAGE_DOWN"}


def _build_claim(
    pay: Optional[str],
    payda: Optional[str],
    value: Optional[float],
    value_type: str,
    deadline: Optional[str],
) -> Optional[FinancialClaim]:
    """Assemble a FinancialClaim under the Anchor Rule.

    Entry gate (what may become a claim at all):
    * pay (asset) is mandatory — no pay → None.
    * pay plus at least one of value or deadline → create the object (missing
      fields stay None).
    * pay with neither value nor deadline → None (asset-only prose is discarded).

    Status (HARD vs INCOMPLETE) is unchanged: all four of pay, payda, value and
    deadline must be present for HARD_CLAIM; anything else is INCOMPLETE_CLAIM.
    """
    if pay is None:
        return None
    if value is None and deadline is None:
        return None  # asset alone — not a claim
    if payda == pay:
        payda = None
    status = (
        "HARD_CLAIM"
        if (pay and payda and value is not None and deadline)
        else "INCOMPLETE_CLAIM"
    )
    try:
        return FinancialClaim(
            pay=pay,
            payda=payda,
            value=float(value) if value is not None else None,
            value_type=value_type,
            deadline=deadline,
            status=status,
        )
    except Exception:
        return None


def _extract_single_claim(
    text: str,
    fallback_deadline: Optional[str] = None,
    base_date: Optional[datetime] = None,
) -> Optional[FinancialClaim]:
    """Standard single-claim extraction over one (sub-)clause."""
    text = text.strip()
    if not text:
        return None
    # Numbers consumed by a time expression ("2 hafta") must not double as a
    # price, so scan deadlines up front and feed their spans to the value pool.
    deadlines = _scan_deadline_mentions(text, base_date)
    deadline = extract_deadline(text, base_date) or fallback_deadline
    value_type = _detect_value_type(text, None)
    pay, payda = _extract_pair_assets(text)

    if _is_percentage_type(value_type):
        value, value_end = _extract_percentage_value(text)
        unit_payda = None
    else:
        value, unit_payda, value_end = _extract_value_with_payda(text, deadlines)
    if value is None:
        value, value_end = _extract_best_numeric_value(text, deadlines)

    if not pay:
        pay = _extract_primary_asset(text)
    if not pay:
        return None

    # Anchor Rule: need asset + (value OR deadline); value-only or deadline-only OK.
    if value is None and deadline is None:
        return None

    if not payda:
        payda = _extract_payda_near_value(text, value_end, pay)
    if not payda and unit_payda and unit_payda != pay:
        payda = unit_payda
    if _is_percentage_type(value_type) and not payda:
        payda = _extract_base_payda_from_text(text)

    return _build_claim(pay, payda, value, value_type, deadline)


# ---- STRATEGY A: punctuation & conjunction splitting ----------------------
def _strategy_punctuation_split(text: str, base_date: Optional[datetime] = None) -> List[FinancialClaim]:
    """Split text into clauses on punctuation / conjunctions, extract per clause.

    Best for well-punctuated input where each clause is one independent claim.
    A text-level deadline is used as a fallback so a date mentioned once
    ("... yıl sonunda ...") still applies to sibling clauses.
    """
    global_deadline = extract_deadline(text, base_date)
    claims: List[FinancialClaim] = []
    for clause in _CLAUSE_SPLIT_RE.split(text):
        if not clause or not clause.strip():
            continue
        claim = _extract_single_claim(clause, fallback_deadline=global_deadline, base_date=base_date)
        if claim:
            claims.append(claim)
    return claims


# ---- STRATEGY B: hierarchical pair / number proximity scan ----------------
def _find_locked_pairs(text: str) -> List[dict]:
    """Locate 'X/Y', 'X-Y' and natural-language parity locks as single blocks."""
    pairs: List[dict] = []

    def _append_pair(pay: str, payda: str, start: int, end: int) -> None:
        if not pay or not payda or pay == payda:
            return
        if any(not (end <= p["start"] or start >= p["end"]) for p in pairs):
            return
        pairs.append({"pay": pay, "payda": payda, "start": start, "end": end})

    for m in re.finditer(
        r"([A-Za-zÇĞİÖŞÜçğıöşü]{2,20})\s{0,500}[/\-]\s{0,500}([A-Za-zÇĞİÖŞÜçğıöşü]{2,20})",
        text,
    ):
        _append_pair(map_asset_token(m.group(1)), map_asset_token(m.group(2)), m.start(), m.end())

    # Natural-language parity: "türk lirası dolar karşısında", "dolar lira paritesi"
    nl_pattern = re.compile(
        r"((?:[A-Za-zÇĞİÖŞÜçğıöşü]+\s+){0,2}[A-Za-zÇĞİÖŞÜçğıöşü]+)\s+"
        r"(?:ile\s+)?"
        r"((?:[A-Za-zÇĞİÖŞÜçğıöşü]+\s+){0,2}[A-Za-zÇĞİÖŞÜçğıöşü]+)\s+"
        r"(?:karşısında|karsisinda|paritesi)",
        re.IGNORECASE,
    )
    for m in nl_pattern.finditer(text):
        _append_pair(
            map_asset_token(m.group(1).strip()),
            map_asset_token(m.group(2).strip()),
            m.start(),
            m.end(),
        )

    return pairs


def _scan_asset_mentions(text: str) -> List[dict]:
    """Ordered single-asset mentions with positions (longest n-gram wins)."""
    mentions: List[dict] = []
    words = list(re.finditer(r"[A-Za-zÇĞİÖŞÜçğıöşü]+|[$€₺]", text))
    i = 0
    while i < len(words):
        token = words[i].group(0)
        if token in _SYMBOL_ASSETS:
            mentions.append({"ticker": _SYMBOL_ASSETS[token], "start": words[i].start(), "end": words[i].end()})
            i += 1
            continue
        matched = False
        for n in (3, 2, 1):  # prefer multi-word names ("binance coin")
            if i + n > len(words):
                continue
            span_start, span_end = words[i].start(), words[i + n - 1].end()
            # Never join words across a number ("BTC 100k dolar" must stay 3 mentions).
            if n > 1 and re.search(r"\d", text[span_start:span_end]):
                continue
            phrase = " ".join(w.group(0) for w in words[i:i + n])
            # Fuzzy typo-correction only for single words; multi-word spans must
            # match an alias exactly (else "k dolar" fuzzy-maps to "dolar").
            ticker = map_asset_token(phrase, allow_multi_token=False, allow_fuzzy=(n == 1))
            if ticker:
                mentions.append({"ticker": ticker, "start": span_start, "end": span_end})
                i += n
                matched = True
                break
        if not matched:
            i += 1
    return mentions


def _overlaps_any_pair(mention: dict, pairs: List[dict]) -> bool:
    return any(p["start"] <= mention["start"] < p["end"] for p in pairs)


def _adjacent_pair_index(pairs, used_pairs, free_mentions, numbers, nstart, nend) -> Optional[int]:
    """Closest unused pair with no other asset / number between it and the number."""
    best, best_dist = None, None
    for idx, p in enumerate(pairs):
        if idx in used_pairs:
            continue
        if p["end"] <= nstart:        # pair sits on the left of the number
            lo, hi, dist = p["end"], nstart, nstart - p["end"]
        elif p["start"] >= nend:      # pair sits on the right of the number
            lo, hi, dist = nend, p["start"], p["start"] - nend
        else:                          # overlapping (rare)
            lo, hi, dist = nstart, nend, 0
        if any(lo <= fm["start"] < hi for fm in free_mentions):
            continue
        if any(lo <= s < hi for (_v, s, _e) in numbers if s != nstart):
            continue
        if best_dist is None or dist < best_dist:
            best, best_dist = idx, dist
    return best


def _mention_number_distance(mention: dict, nstart: int, nend: int) -> int:
    """Character gap between a mention and a number span (0 if overlapping).

    Works for any positional mention (asset OR deadline) that carries
    ``start`` / ``end`` keys.
    """
    if mention["end"] <= nstart:
        return nstart - mention["end"]
    if mention["start"] >= nend:
        return mention["start"] - nend
    return 0


def _scan_deadline_mentions(text: str, base_date: Optional[datetime] = None) -> List[dict]:
    """Locate every time expression in ``text`` with its position and ISO date.

    Returns an ordered (by ``start``) list of ``{"start", "end", "date"}`` dicts,
    the deadline counterpart of :func:`_scan_asset_mentions`. This lets Strategy B
    bind each number to its *nearest* date instead of smearing a single global
    deadline over the whole sentence. Patterns mirror :func:`extract_deadline`;
    higher-priority spans (explicit dates, numeric durations) are recorded first
    and an occupancy guard prevents a later, looser pattern (e.g. "hafta\\w*")
    from double-counting a region already claimed (e.g. "2 hafta").
    """
    now = base_date if base_date is not None else datetime.now()
    lowered = _lower_text(text)
    mentions: List[dict] = []
    occupied: List[tuple] = []  # (start, end) spans already consumed

    def add(start: int, end: int, date: Optional[str]) -> None:
        if not date:
            return
        if any(not (end <= rs or start >= re_) for rs, re_ in occupied):
            return  # overlaps a higher-priority mention
        occupied.append((start, end))
        mentions.append({"start": start, "end": end, "date": date})

    # 1) Explicit numeric dates (highest priority) -------------------------
    for m in re.finditer(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            add(m.start(), m.end(), _iso(y, mo, d))
    for m in re.finditer(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b", text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            add(m.start(), m.end(), _iso(y, mo, d))

    # 2) Month name + day / day + month name -------------------------------
    for m in re.finditer(
        rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?!\s{{0,500}}%)(?:,?\s{{0,500}}(20\d{{2}}))?",
        lowered,
    ):
        month, day = _ALL_MONTHS[m.group(1)], int(m.group(2))
        year = int(m.group(3)) if m.group(3) else _year_in_text(lowered, base_date)
        if 1 <= day <= _last_day_of_month(year, month):
            add(m.start(), m.end(), _iso(year, month, day))
    for m in re.finditer(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_ALT})\b(?:,?\s{{0,500}}(20\d{{2}}))?",
        lowered,
    ):
        day, month = int(m.group(1)), _ALL_MONTHS[m.group(2)]
        year = int(m.group(3)) if m.group(3) else _year_in_text(lowered, base_date)
        if 1 <= day <= _last_day_of_month(year, month):
            add(m.start(), m.end(), _iso(year, month, day))

    # 3) Numeric durations (before bare relative week/month) ---------------
    # Turkish unit stems take a trailing \w* so inflected forms are still caught
    # as a single span ("2 haftaya", "3 güne", "2 ayda"); this keeps the leading
    # digit inside the deadline so it never bleeds into the value buckets.
    def _lead_int(span: str) -> int:
        return int(re.match(r"\d{1,500}", span).group(0))

    for m in re.finditer(r"\d{1,500}\s{0,500}(?:hafta\w{0,500}|weeks?)\b", lowered):
        add(m.start(), m.end(), (now + timedelta(weeks=_lead_int(m.group(0)))).strftime("%Y-%m-%d"))
    for m in re.finditer(r"\d{1,500}\s{0,500}(?:gün\w{0,500}|gun\w{0,500}|days?)\b", lowered):
        add(m.start(), m.end(), (now + timedelta(days=_lead_int(m.group(0)))).strftime("%Y-%m-%d"))
    for m in re.finditer(r"\d{1,500}\s{0,500}(?:ay\w{0,500}|months?)\b", lowered):
        add(m.start(), m.end(), (now + timedelta(days=_lead_int(m.group(0)) * 30)).strftime("%Y-%m-%d"))
    for m in re.finditer(r"\d{1,500}\s{0,500}(?:yıl\w{0,500}|yil\w{0,500}|years?)\b", lowered):
        add(m.start(), m.end(), (now + timedelta(days=_lead_int(m.group(0)) * 365)).strftime("%Y-%m-%d"))

    # 4) Relative day expressions (inflection-tolerant) --------------------
    for m in re.finditer(r"\b(?:bugün|bugun)\w{0,500}|\btoday\b", lowered):
        add(m.start(), m.end(), now.strftime("%Y-%m-%d"))
    for m in re.finditer(r"\b(?:yarın|yarin)\w{0,500}|\btomorrow\b", lowered):
        add(m.start(), m.end(), (now + timedelta(days=1)).strftime("%Y-%m-%d"))
    for m in re.finditer(
        r"\b(?:hafta\w{0,500}|gelecek hafta|önümüzdeki hafta|onumuzdeki hafta)\b|\bnext week\b",
        lowered,
    ):
        add(m.start(), m.end(), (now + timedelta(days=7)).strftime("%Y-%m-%d"))
    for m in re.finditer(
        r"\b(?:gelecek|önümüzdeki|onumuzdeki)\s+ay\w{0,500}|\bnext month\b",
        lowered,
    ):
        add(m.start(), m.end(), (now + timedelta(days=30)).strftime("%Y-%m-%d"))

    # 5) Year-end / EOY ----------------------------------------------------
    for m in re.finditer(
        r"\beoy\b|yıl sonu\w{0,500}|yil sonu\w{0,500}|sene sonu\w{0,500}|yıl sonuna kadar|"
        r"end of (?:the )?year|year[- ]end|by year[- ]end",
        lowered,
    ):
        add(m.start(), m.end(), f"{_year_in_text(lowered, base_date)}-12-31")

    # 6) End of month / EOM ------------------------------------------------
    for m in re.finditer(r"\beom\b|ay sonu\w{0,500}|month[- ]end|end of (?:the )?month", lowered):
        add(m.start(), m.end(), _iso(now.year, now.month, base_date=base_date))

    # 7) Short / medium / long term ----------------------------------------
    for m in re.finditer(r"\b(?:kısa\s+vade(?:li|de)?|short(?:\s|-)?term)\b", lowered):
        add(m.start(), m.end(), (now + timedelta(days=30)).strftime("%Y-%m-%d"))
    for m in re.finditer(r"\b(?:orta\s+vade(?:li|de)?|medium(?:\s|-)?term|mid(?:\s|-)?term)\b", lowered):
        add(m.start(), m.end(), (now + timedelta(days=365)).strftime("%Y-%m-%d"))
    for m in re.finditer(r"\b(?:uzun\s+vade(?:li|de)?|long(?:\s|-)?term)\b", lowered):
        add(m.start(), m.end(), (now + timedelta(days=1000)).strftime("%Y-%m-%d"))

    # 8) Upcoming / next year ----------------------------------------------
    for m in re.finditer(
        r"\b(?:gelecek|önümüzdeki|onumuzdeki|ertesi)\s+yıl\w{0,500}|\bnext year\b",
        lowered,
    ):
        add(m.start(), m.end(), (now + timedelta(days=365)).strftime("%Y-%m-%d"))

    # 9) Financial quarters (positional) -------------------------------------
    for m in re.finditer(r"\bq\s{0,500}([1-4])\b|\b([1-4])\s{0,500}\.?\s{0,500}(?:çeyre\w{0,500}|quarter\w{0,500})", lowered):
        q = int(m.group(1) or m.group(2))
        year = _year_in_text(lowered, base_date)
        mo, d = _QUARTER_END[q]
        add(m.start(), m.end(), _iso(year, mo, d))
    for pattern, q in (
        (r"\b(?:ilk çeyre\w{0,500}|first quarter|1st quarter)", 1),
        (r"\b(?:ikinci çeyre\w{0,500}|second quarter|2nd quarter)", 2),
        (r"\b(?:üçüncü çeyre\w{0,500}|uçuncu çeyre\w{0,500}|third quarter|3rd quarter)", 3),
        (r"\b(?:dördüncü çeyre\w{0,500}|dorduncu çeyre\w{0,500}|fourth quarter|4th quarter)", 4),
    ):
        for m in re.finditer(pattern, lowered):
            year = _year_in_text(lowered, base_date)
            mo, d = _QUARTER_END[q]
            add(m.start(), m.end(), _iso(year, mo, d))

    # 10) Financial halves (positional) ------------------------------------
    for m in re.finditer(r"\b(?:h1|1h)\b", lowered):
        add(m.start(), m.end(), _iso(_year_in_text(lowered, base_date), 6, 30))
    for m in re.finditer(r"\b(?:h2|2h)\b", lowered):
        add(m.start(), m.end(), _iso(_year_in_text(lowered, base_date), 12, 31))
    for m in re.finditer(
        r"\b(?:ilk yar[ıi]\w{0,500}|yılın ilk yar[ıi]\w{0,500}|first half|1st half)", lowered
    ):
        add(m.start(), m.end(), _iso(_year_in_text(lowered, base_date), 6, 30))
    for m in re.finditer(
        r"\b(?:ikinci yar[ıi]\w{0,500}|yılın ikinci yar[ıi]\w{0,500}|second half|2nd half)", lowered
    ):
        add(m.start(), m.end(), _iso(_year_in_text(lowered, base_date), 12, 31))

    # 11) Verbal year phrases ("2027 başında", "2028 sonu") ----------------
    for m in re.finditer(r"\b(20\d{2})\s{0,500}(baş\w{0,500}|son\w{0,500}|yıl\w{0,500}|için\w{0,500}|icin\w{0,500})?\b", lowered):
        year = int(m.group(1))
        suffix = (m.group(2) or "").lower()
        if suffix.startswith("baş") or suffix.startswith("bas"):
            date = f"{year}-01-01"
        elif suffix.startswith("son"):
            date = f"{year}-12-31"
        elif suffix:
            date = f"{year}-12-31"
        else:
            continue  # bare year without temporal cue — not a deadline span
        add(m.start(), m.end(), date)

    mentions.sort(key=lambda d: d["start"])
    return mentions


def _nearest_deadline(
    deadlines: List[dict], nstart: int, nend: int, fallback: Optional[str]
) -> Optional[str]:
    """Closest deadline (by character distance) to a number span, else fallback."""
    best, best_dist = None, None
    for dl in deadlines:
        dist = _mention_number_distance(dl, nstart, nend)
        if best_dist is None or dist < best_dist:
            best, best_dist = dl, dist
    return best["date"] if best is not None else fallback


def _number_inside_deadline(nstart: int, nend: int, deadlines: List[dict]) -> bool:
    """True when a number span lies inside a deadline expression ("Number Bleeding").

    Duration deadlines ("5 hafta", "3 gün", "2 ay") are scanned with their leading
    digits included, so the bare number sits *within* the deadline span. Such a
    number is a time unit, not a financial value, and must be kept out of the value
    buckets. Non-duration deadlines ("yarın", "haftayı", "yıl sonu") carry no digits,
    so a real value sitting next to one ("... haftayı 50 lira") never overlaps and
    is preserved.
    """
    return any(nstart < dl["end"] and dl["start"] < nend for dl in deadlines)


def _strategy_hierarchical_proximity(text: str, base_date: Optional[datetime] = None) -> List[FinancialClaim]:
    """Punctuation-agnostic scan via Proximity Bucketing.

    1) Pair lock: numbers sitting next to a locked 'X/Y' pair take pay+payda
       from it.
    2) Bucketing: every remaining free asset is assigned ("zimmetlenir") to the
       single nearest free number by character distance. On an exact tie the
       asset goes to the RIGHT number, because a centred asset ("100k | euro |
       50") is the subject/pay of the claim that is just starting.
    3) In-bucket binding: within a number's own bucket, the nearest asset to the
       LEFT is pay and the nearest to the RIGHT is payda. If the bucket has no
       left asset, the right asset becomes pay (not payda). This makes asset
       stealing between numbers structurally impossible.
    4) Anchor fallback: free assets that never bound to a number but sit next to
       a deadline produce an INCOMPLETE claim (value=None) under the Anchor Rule.
    """
    value_type = _detect_value_type(text, None)
    # Proximity deadlines: bind each number to its NEAREST date instead of
    # smearing one global deadline over every claim. The first date found acts
    # as the fallback for numbers that have no date of their own (extract_deadline
    # is used as an extra safety net only when the scan finds nothing positional).
    deadlines = _scan_deadline_mentions(text, base_date)
    global_fallback_deadline = (
        deadlines[0]["date"] if deadlines else extract_deadline(text, base_date)
    )
    pairs = _find_locked_pairs(text)
    mentions = _scan_asset_mentions(text)
    free_mentions = [m for m in mentions if not _overlaps_any_pair(m, pairs)]
    # Number-role hierarchy: a number that is a percentage magnitude (for a
    # PRICE claim) or sits inside a deadline span ("2 hafta") is consumed by a
    # higher-priority role and can never be a price target.
    numbers = [
        (v, s, e) for (v, s, e) in _scan_number_groups(text)
        if not _in_period_context(text, s, e)
        and not _number_inside_deadline(s, e, deadlines)
        and not (not _is_percentage_type(value_type) and _number_is_percentage(text, s, e))
    ]

    used_pairs: set = set()
    ordered_claims: List[tuple] = []  # (position, claim) -> sorted at the end

    # 1) PAIR LOCK -----------------------------------------------------------
    paired_number_idx: set = set()
    for ni, (value, nstart, nend) in enumerate(numbers):
        pair_idx = _adjacent_pair_index(pairs, used_pairs, free_mentions, numbers, nstart, nend)
        if pair_idx is None:
            continue
        used_pairs.add(pair_idx)
        paired_number_idx.add(ni)
        claim = _build_claim(
            pairs[pair_idx]["pay"],
            pairs[pair_idx]["payda"],
            value,
            value_type,
            _nearest_deadline(deadlines, nstart, nend, global_fallback_deadline),
        )
        if claim:
            ordered_claims.append((nstart, claim))

    free_numbers = [(ni, numbers[ni]) for ni in range(len(numbers)) if ni not in paired_number_idx]

    # 2) DISTANCE BUCKETING --------------------------------------------------
    buckets: dict = {ni: [] for ni, _ in free_numbers}
    if free_numbers:
        for mention in free_mentions:
            best_ni, best_dist, best_pos = None, None, None
            for ni, (_v, ns, ne) in free_numbers:
                dist = _mention_number_distance(mention, ns, ne)
                # Strictly closer wins; on a tie the right-most number wins.
                if best_dist is None or dist < best_dist or (dist == best_dist and ns > best_pos):
                    best_ni, best_dist, best_pos = ni, dist, ns
            buckets[best_ni].append(mention)

    # 3) IN-BUCKET BINDING ---------------------------------------------------
    for ni, (value, nstart, nend) in free_numbers:
        bucket = buckets[ni]
        left = [m for m in bucket if m["end"] <= nstart]
        right = [m for m in bucket if m["start"] >= nend]

        pay = payda = None
        if left:
            pay = max(left, key=lambda m: m["end"])["ticker"]        # nearest on the left
        if right:
            nearest_right = min(right, key=lambda m: m["start"])["ticker"]  # nearest on the right
            if pay is None:
                pay = nearest_right                                   # no left asset -> right is pay
            elif nearest_right != pay:
                payda = nearest_right

        if _is_percentage_type(value_type) and not payda:
            payda = _extract_base_payda_from_text(text)

        # Bind this number to the date physically closest to it.
        final_deadline = _nearest_deadline(deadlines, nstart, nend, global_fallback_deadline)
        claim = _build_claim(pay, payda, value, value_type, final_deadline)
        if claim:
            ordered_claims.append((nstart, claim))

    # 4) ANCHOR — unbound assets with a nearby deadline, no price number ----
    # When the text has no usable value ("Dolar haftaya lira olur") every asset
    # mention may fail to bind to a number. Any leftover asset that sits next to
    # a deadline still forms an INCOMPLETE claim (value=None) under the Anchor Rule.
    bound_pay = {c.pay for _pos, c in ordered_claims}
    bound_payda = {c.payda for _pos, c in ordered_claims if c.payda}

    for mention in free_mentions:
        if mention["ticker"] in bound_pay or mention["ticker"] in bound_payda:
            continue
        anchor_deadline = _nearest_deadline(
            deadlines, mention["start"], mention["end"], global_fallback_deadline
        )
        if not anchor_deadline:
            continue
        anchor_payda = None
        for other in free_mentions:
            if other is mention or other["ticker"] == mention["ticker"]:
                continue
            dist = _mention_number_distance(other, mention["start"], mention["end"])
            if dist <= 40:  # same local phrase — treat as denominator candidate
                anchor_payda = other["ticker"]
                break
        claim = _build_claim(
            mention["ticker"], anchor_payda, None, value_type, anchor_deadline
        )
        if claim:
            ordered_claims.append((mention["start"], claim))
            bound_pay.add(mention["ticker"])
            if anchor_payda:
                bound_payda.add(anchor_payda)

    ordered_claims.sort(key=lambda item: item[0])
    return [claim for _pos, claim in ordered_claims]


# ---- Scoring / noise reduction --------------------------------------------
def _count_status(claims: List[FinancialClaim], status: str) -> int:
    return sum(1 for c in claims if c.status == status)


def _select_best_results(
    results_a: List[FinancialClaim], results_b: List[FinancialClaim]
) -> List[FinancialClaim]:
    """3-stage noise reduction: recall (HARD) -> precision (INCOMPLETE) -> tie to B.

    Coverage (raw claim count) is intentionally NOT used — a strategy that
    produces extra INCOMPLETE junk must not beat a cleaner rival.
    """
    hard_a, hard_b = _count_status(results_a, "HARD_CLAIM"), _count_status(results_b, "HARD_CLAIM")
    if hard_a != hard_b:  # 1) Recall: more HARD_CLAIMs wins.
        return results_a if hard_a > hard_b else results_b

    poss_a, poss_b = _count_status(results_a, "INCOMPLETE_CLAIM"), _count_status(results_b, "INCOMPLETE_CLAIM")
    if poss_a != poss_b:  # 2) Precision: fewer INCOMPLETE_CLAIMs (cleaner) wins.
        return results_a if poss_a < poss_b else results_b

    return results_b  # 3) Tie: B is more robust on inverted / unpunctuated text.


# ---------------------------------------------------------------------------
# Main entry point (RegEx-only, ensemble of Strategy A + Strategy B)
# ---------------------------------------------------------------------------
def rule_based_claims_from_prompt(
    prompt: str, base_date: Optional[datetime] = None
) -> List[FinancialClaim]:
    """Ensemble extraction: run both strategies and return the cleaner result.

    Pass ``base_date`` to resolve relative deadlines against a fixed instant
    (e.g. the original publish time of an archived post); it defaults to
    ``datetime.now()`` so existing call sites are unaffected.
    """
    text = prompt.strip()
    if not text:
        return []
    results_a = _strategy_punctuation_split(text, base_date)
    results_b = _strategy_hierarchical_proximity(text, base_date)
    return _select_best_results(results_a, results_b)
