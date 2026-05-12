from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import get_close_matches
from typing import Optional

# ---------------------------------------------------------------------------
# Asset whitelists
# ---------------------------------------------------------------------------

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "TRY", "AUD", "CAD", "NZD", "CNY"]
CRYPTO = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE", "DOT", "LINK"]
STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
    "NFLX", "AMD", "INTC", "COIN", "PYPL", "PLTR", "UBER", "DIS",
]
TOTAL_WHITELIST: list[str] = CURRENCIES + CRYPTO + STOCKS

_TICKER_MAP: dict[str, str] = {t.lower(): t for t in TOTAL_WHITELIST}

_ALIAS_MAP: dict[str, str] = {
    # Fiat
    "dolar": "USD", "doları": "USD", "dolari": "USD",
    "amerikan doları": "USD", "abd doları": "USD",
    "us dollar": "USD", "u.s. dollar": "USD", "dollar": "USD",
    "dolr": "USD", "doller": "USD", "dolarrr": "USD",
    "avro": "EUR", "euro": "EUR", "euor": "EUR",
    "sterlin": "GBP", "ingiliz sterlini": "GBP", "pound": "GBP", "british pound": "GBP",
    "yen": "JPY", "japon yeni": "JPY",
    "frank": "CHF", "swiss franc": "CHF", "isvicre frangi": "CHF", "isviçre frangı": "CHF",
    "lira": "TRY", "turkish lira": "TRY", "turk lirasi": "TRY", "türk lirası": "TRY",
    "kanada doları": "CAD", "avustralya doları": "AUD",
    "yeni zelanda doları": "NZD", "çin yuanı": "CNY",
    "australian dollar": "AUD", "canadian dollar": "CAD",
    "new zealand dollar": "NZD", "yuan": "CNY", "renminbi": "CNY",
    # Crypto
    "bitcoin": "BTC", "bitcoın": "BTC", "bitcon": "BTC", "btcoin": "BTC",
    "ethereum": "ETH", "ether": "ETH", "etherium": "ETH",
    "etheriyum": "ETH", "etheryum": "ETH", "ethirium": "ETH",
    "solana": "SOL", "solona": "SOL",
    "binance coin": "BNB", "bnb coin": "BNB",
    "ripple": "XRP", "cardano": "ADA", "avalanche": "AVAX",
    "dogecoin": "DOGE", "polkadot": "DOT", "chainlink": "LINK",
    # Stocks
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "nvidia": "NVDA", "tesla": "TSLA", "meta": "META",
    "netflix": "NFLX", "amd": "AMD", "intel": "INTC", "coinbase": "COIN",
    "paypal": "PYPL", "palantir": "PLTR", "uber": "UBER",
    "disney": "DIS", "walt disney": "DIS",
    # Common typos
    "microsof": "MSFT", "gogle": "GOOGL", "amazn": "AMZN",
    "nvida": "NVDA", "tesl": "TSLA", "netfliix": "NFLX",
}

_ALIAS_POOL: list[str] = list(_ALIAS_MAP) + list(_TICKER_MAP)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FinancialClaim:
    pay: Optional[str]
    payda: Optional[str]
    value: Optional[float]
    value_type: str          # "PRICE" | "PERCENTAGE_UP" | "PERCENTAGE_DOWN"
    deadline: Optional[str]  # ISO date string or None
    status: str              # "HARD_CLAIM" | "POSSIBLE_CLAIM"

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
# Asset mapping
# ---------------------------------------------------------------------------

def map_asset_token(token: str) -> Optional[str]:
    normalized = re.sub(r"[^a-zA-ZÇĞİÖŞÜçğıöşü\s]", "", token.strip().lower())
    upper = token.strip().upper()

    if upper in TOTAL_WHITELIST:
        return upper

    mapped = _TICKER_MAP.get(normalized) or _ALIAS_MAP.get(normalized)
    if mapped:
        return mapped

    close = get_close_matches(normalized, _ALIAS_POOL, n=1, cutoff=0.82)
    if close:
        mapped = _ALIAS_MAP.get(close[0]) or _TICKER_MAP.get(close[0])
        if mapped in TOTAL_WHITELIST:
            return mapped

    for part in normalized.split():
        mapped = _ALIAS_MAP.get(part) or _TICKER_MAP.get(part)
        if mapped in TOTAL_WHITELIST:
            return mapped

    return None


# ---------------------------------------------------------------------------
# Deadline extraction
# ---------------------------------------------------------------------------

_now = datetime.now()


def _extract_year_end_deadline(text: str) -> Optional[str]:
    lowered = text.lower()
    patterns = [
        r"(20\d{2})\D{0,25}(yıl sonu|yıl sonunda|yıl sonuna kadar|sene sonu|sene sonunda|sonunda|end of year|year[- ]end|by year[- ]end)",
        r"(yıl sonu|yıl sonunda|yıl sonuna kadar|sene sonu|sene sonunda|end of year|year[- ]end|by year[- ]end)\D{0,25}(20\d{2})",
        r"(end of)\D{0,10}(20\d{2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, lowered)
        if not m:
            continue
        year = next((g for g in m.groups() if g and g.isdigit()), None)
        if year:
            return f"{year}-12-31"
    return None


def _extract_relative_deadline(text: str) -> Optional[str]:
    lowered = text.lower()
    if re.search(r"\b(kısa\s+vade(li|de)?|short(\s|-)?term)\b", lowered):
        return (_now + timedelta(days=30)).strftime("%Y-%m-%d")
    if re.search(r"\b(orta\s+vade(li|de)?|medium(\s|-)?term|mid(\s|-)?term)\b", lowered):
        return (_now + timedelta(days=365)).strftime("%Y-%m-%d")
    if re.search(r"\b(uzun\s+vade(li|de)?|long(\s|-)?term)\b", lowered):
        return (_now + timedelta(days=1000)).strftime("%Y-%m-%d")
    return None


def extract_deadline(text: str) -> Optional[str]:
    year_end = _extract_year_end_deadline(text)
    if year_end:
        return year_end

    # Check for explicit YYYY-MM-DD
    iso_date = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso_date:
        return iso_date.group(1)

    lowered = text.lower()
    if re.search(r"yıl sonu|yıl sonunda|yıl sonuna kadar|yıl sonu itibarıyla|end of year|year[- ]end|by year[- ]end", lowered):
        return f"{_now.year}-12-31"
    if "haftaya" in lowered or "next week" in lowered:
        return (_now + timedelta(days=7)).strftime("%Y-%m-%d")

    relative = _extract_relative_deadline(text)
    if relative:
        return relative

    day_m = re.search(r"(\d+)\s*(gün)\s*(içinde|sonra)|(\d+)\s*(day|days)\s*(in|within|later|after)", lowered)
    if day_m:
        val = next((g for g in day_m.groups() if g and g.isdigit()), None)
        if val:
            return (_now + timedelta(days=int(val))).strftime("%Y-%m-%d")

    month_m = re.search(r"(\d+)\s*(ay)\s*(içinde|sonra)|(\d+)\s*(month|months)\s*(in|within|later|after)", lowered)
    if month_m:
        val = next((g for g in month_m.groups() if g and g.isdigit()), None)
        if val:
            return (_now + timedelta(days=int(val) * 30)).strftime("%Y-%m-%d")

    year_m = re.search(r"(\d+)\s*(yıl)\s*(içinde|sonra)|(\d+)\s*(year|years)\s*(in|within|later|after)", lowered)
    if year_m:
        val = next((g for g in year_m.groups() if g and g.isdigit()), None)
        if val:
            return (_now + timedelta(days=int(val) * 365)).strftime("%Y-%m-%d")

    explicit_year = re.search(r"\b(20\d{2})\b", lowered)
    if explicit_year and re.search(r"başında|sonunda|yıl|end|year", lowered):
        return f"{explicit_year.group(1)}-12-31"

    return None


# ---------------------------------------------------------------------------
# Value extraction
# ---------------------------------------------------------------------------

def _extract_pair_assets(text: str) -> tuple[Optional[str], Optional[str]]:
    m = re.search(r"([A-Za-zÇĞİÖŞÜçğıöşü]{2,20})\s*/\s*([A-Za-zÇĞİÖŞÜçğıöşü]{2,20})", text)
    if not m:
        return None, None
    return map_asset_token(m.group(1)), map_asset_token(m.group(2))


def _extract_value_with_payda(text: str) -> tuple[Optional[float], Optional[str], int]:
    pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*([A-Za-zÇĞİÖŞÜçğıöşü$€₺]{2,12})")
    candidates: list[tuple[float, Optional[str], int]] = []
    for m in pattern.finditer(text):
        try:
            val = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        unit = map_asset_token(m.group(2))
        candidates.append((val, unit, m.end()))
    if not candidates:
        return None, None, -1
    return candidates[-1]


def _extract_best_numeric_value(text: str) -> tuple[Optional[float], int]:
    lowered = text.lower()
    time_units = {"gün", "day", "days", "ay", "month", "months", "yıl", "year", "years"}
    filtered: list[re.Match] = []
    for m in re.finditer(r"\d+(?:[.,]\d+)?", text):
        try:
            val = float(m.group(0).replace(",", "."))
        except ValueError:
            continue
        tail = lowered[m.end(): m.end() + 15]
        if any(unit in tail for unit in time_units):
            continue
        if 1900 <= val <= 2100 and re.search(r"end|year|yıl|sonu|baş", lowered):
            continue
        filtered.append(m)

    target = filtered[-1] if filtered else None
    if not target:
        all_matches = list(re.finditer(r"\d+(?:[.,]\d+)?", text))
        target = all_matches[-1] if all_matches else None
    if not target:
        return None, -1
    try:
        return float(target.group(0).replace(",", ".")), target.end()
    except ValueError:
        return None, -1


def _extract_percentage_value(text: str) -> tuple[Optional[float], int]:
    patterns = [
        r"%\s*(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*%",
        r"y[uü]zde\s*(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*percent",
    ]
    lowered = text.lower()
    for pattern in patterns:
        m = re.search(pattern, lowered, flags=re.IGNORECASE)
        if not m:
            continue
        try:
            return float(m.group(1).replace(",", ".")), m.end()
        except ValueError:
            continue
    return None, -1


# ---------------------------------------------------------------------------
# Type / direction detection
# ---------------------------------------------------------------------------

_UP_KEYWORDS = [
    "artış", "artis", "yükselecek", "yukselecek", "değer kazanacak", "deger kazanacak",
    "increase", "rise", "up", "gain", "higher",
]
_DOWN_KEYWORDS = [
    "azalış", "azalis", "düşecek", "dusecek", "değer kaybedecek", "deger kaybedecek",
    "decrease", "drop", "fall", "down", "lower",
]


def _detect_value_type(text: str) -> str:
    lowered = text.lower()
    has_percent = "%" in lowered or "yüzde" in lowered or "yuzde" in lowered or "percent" in lowered
    if has_percent or any(k in lowered for k in _UP_KEYWORDS + _DOWN_KEYWORDS):
        if any(k in lowered for k in _DOWN_KEYWORDS):
            return "PERCENTAGE_DOWN"
        return "PERCENTAGE_UP"
    return "PRICE"


# ---------------------------------------------------------------------------
# Asset helpers
# ---------------------------------------------------------------------------

def _extract_primary_asset(text: str) -> Optional[str]:
    tokens = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", text)
    for n in (1, 2, 3):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i: i + n])
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


def _extract_base_payda_from_text(text: str) -> Optional[str]:
    lowered = text.lower()
    base_patterns = [
        r"([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})\s+baz[ıi]nda",
        r"([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})\s+kar[sş][ıi]s[ıi]nda",
        r"against\s+([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})",
        r"versus\s+([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})",
        r"vs\.?\s*([A-Za-zÇĞİÖŞÜçğıöşü]{2,15})",
    ]
    for pattern in base_patterns:
        m = re.search(pattern, lowered, flags=re.IGNORECASE)
        if not m:
            continue
        mapped = map_asset_token(m.group(1))
        if mapped:
            return mapped
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def rule_based_claims_from_prompt(prompt: str) -> list[FinancialClaim]:
    text = prompt.strip()
    deadline = extract_deadline(text)
    value_type = _detect_value_type(text)
    pay, payda = _extract_pair_assets(text)

    if value_type in {"PERCENTAGE_UP", "PERCENTAGE_DOWN"}:
        value, value_end = _extract_percentage_value(text)
        unit_payda = None
    else:
        value, unit_payda, value_end = _extract_value_with_payda(text)

    if value is None:
        value, value_end = _extract_best_numeric_value(text)

    if not pay:
        pay = _extract_primary_asset(text)

    if not pay and value is None:
        return []

    if not payda:
        payda = _extract_payda_near_value(text, value_end, pay)
    if not payda and unit_payda and unit_payda != pay:
        payda = unit_payda
    if value_type in {"PERCENTAGE_UP", "PERCENTAGE_DOWN"} and not payda:
        payda = _extract_base_payda_from_text(text)

    status = (
        "HARD_CLAIM"
        if pay and payda and value is not None and deadline
        else "POSSIBLE_CLAIM"
    )
    return [
        FinancialClaim(
            pay=pay,
            payda=payda,
            value=value,
            value_type=value_type,
            deadline=deadline,
            status=status,
        )
    ]
