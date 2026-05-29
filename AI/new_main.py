from datetime import datetime, timedelta
from typing import Optional, List, Literal
import os
import re
import json
from difflib import get_close_matches
from pydantic import BaseModel, Field, field_validator
from agno.agent import Agent
from agno.models.openai import OpenAIChat

# 1. Modüler Whitelist Tanımları
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "TRY", "AUD", "CAD", "NZD", "CNY"]
CRYPTO = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE", "DOT", "LINK"]
STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "NFLX", "AMD", "INTC", "COIN", "PYPL", "PLTR", "UBER", "DIS"]

# Global kontrol listesi
TOTAL_WHITELIST = CURRENCIES + CRYPTO + STOCKS

# 2. Dinamik Zaman Bilgisi
now = datetime.now()
today_str = now.strftime("%Y-%m-%d")

# 3. Veri Yapısı
class FinancialClaim(BaseModel):
    pay: str = Field(description="Numerator. Whitelist ticker sembolü (Örn: BTC).")
    payda: Optional[str] = Field(None, description="Denominator. Sadece whitelist'te varsa.")
    value: float = Field(description="Saf sayısal miktar.")
    value_type: Literal["PRICE", "PERCENTAGE_UP", "PERCENTAGE_DOWN"] = Field(
        default="PRICE",
        description="Value type: PRICE, PERCENTAGE_UP, or PERCENTAGE_DOWN.",
    )
    deadline: Optional[str] = Field(None, description="ISO formatlı tarih.")
    status: str = Field(description="'HARD_CLAIM' veya 'POSSIBLE_CLAIM'")

    @field_validator("pay")
    def validate_pay(cls, v):
        if v not in TOTAL_WHITELIST:
            raise ValueError(f"Geçersiz Pay: {v}")
        return v

    @field_validator("payda")
    def validate_payda(cls, v):
        if v is not None and v not in TOTAL_WHITELIST:
            return None
        return v

class VeriFiOutput(BaseModel):
    claims: List[FinancialClaim]


class RawClaim(BaseModel):
    pay: Optional[str] = None
    payda: Optional[str] = None
    value: Optional[float] = None
    value_type: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None


class RawVeriFiOutput(BaseModel):
    claims: List[RawClaim]

def build_model() -> OpenAIChat:
    """Use OpenAI when API key exists, otherwise fallback to LM Studio."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return OpenAIChat(id="gpt-4o")
    return OpenAIChat(
        id="mistralai/ministral-3-14b-reasoning",
        base_url="http://localhost:1234/v1",
        api_key="lm-studio",
    )


# 4. Akıllı Agent Yapılandırması
verifi_agent = Agent(
    model=build_model(),
    description="Doğal dili finansal sembollere eşleyen (Mapping) ve ayıklayan motor.",
    markdown=False,
    instructions=[
        f"Today date: {today_str}.",
        "--- MAPPING RULES (TR + EN) ---",
        "1. Map natural names to whitelist ticker symbols.",
        "   - Examples: Bitcoin->BTC, Ethereum->ETH, Dolar/Dollar->USD, Avro/Euro->EUR, Lira->TRY.",
        "   - Company names map to their tickers (Apple->AAPL, Tesla->TSLA, Nvidia->NVDA).",
        f"2. Use only this whitelist: {TOTAL_WHITELIST}",
        "--- TIME CONVERSION RULES ---",
        "3. Do NOT output timeframe. Always write absolute ISO date into deadline when possible.",
        "   - TR: '2026 yıl sonu', '2026 sonunda', 'yıl sonuna kadar' => 2026-12-31 (or current year if year missing)",
        "   - EN: 'end of 2026', 'by year-end 2026' => 2026-12-31",
        "   - TR+EN relative: haftaya/next week, kısa-short, orta-medium, uzun-long term, N day/month/year => convert to date.",
        "4. Use value_type: PRICE, PERCENTAGE_UP, PERCENTAGE_DOWN.",
        "   - If text indicates percentage rise (% / yuzde / artis / yukselecek / deger kazanacak / rise / increase / gain), use PERCENTAGE_UP.",
        "   - If text indicates percentage drop (% / yuzde / azalis / dusecek / fall / decrease / drop), use PERCENTAGE_DOWN.",
        "5. HARD_CLAIM only when pay, payda, value, deadline are all present (4/4). Otherwise POSSIBLE_CLAIM.",
        "6. Return only schema fields. Never include timeframe.",
    ],
)

# Secondary AI extractor: permissive schema, then Python enforces final format.
raw_verifi_agent = Agent(
    model=build_model(),
    markdown=False,
    instructions=[
        f"Today date: {today_str}.",
        "Extract financial claims from Turkish or English text.",
        "Return ONLY JSON with this shape: {'claims':[{'pay':..., 'payda':..., 'value':..., 'value_type':..., 'deadline':..., 'status':...}]}",
        "If uncertain, still provide best-effort fields; leave unknown fields null.",
        "Do not add extra keys, explanations, markdown, or timeframe.",
    ],
)


def extract_year_end_deadline(text: str) -> Optional[str]:
    """If text contains year-end expression, return YYYY-12-31."""
    lowered = text.lower()
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


def extract_relative_deadline(text: str) -> Optional[str]:
    """Convert short/medium/long term phrases to absolute ISO date."""
    lowered = text.lower()
    if re.search(r"\b(kısa\s+vade(li|de)?|short(\s|-)?term)\b", lowered):
        return (now + timedelta(days=30)).strftime("%Y-%m-%d")
    if re.search(r"\b(orta\s+vade(li|de)?|medium(\s|-)?term|mid(\s|-)?term)\b", lowered):
        return (now + timedelta(days=365)).strftime("%Y-%m-%d")
    if re.search(r"\b(uzun\s+vade(li|de)?|long(\s|-)?term)\b", lowered):
        return (now + timedelta(days=1000)).strftime("%Y-%m-%d")
    return None


def extract_claims(output) -> List[FinancialClaim]:
    """Normalize different agent output shapes into FinancialClaim list."""
    if isinstance(output, VeriFiOutput):
        return output.claims

    if isinstance(output, dict) and isinstance(output.get("claims"), list):
        return [FinancialClaim.model_validate(item) for item in output["claims"]]

    if isinstance(output, str):
        cleaned = output.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and isinstance(parsed.get("claims"), list):
                return [FinancialClaim.model_validate(item) for item in parsed["claims"]]
        except json.JSONDecodeError:
            pass

    if hasattr(output, "claims") and isinstance(getattr(output, "claims"), list):
        return [FinancialClaim.model_validate(item) for item in getattr(output, "claims")]

    return []


def extract_raw_claims(output) -> List[RawClaim]:
    """Normalize different output shapes into permissive RawClaim list."""
    if isinstance(output, RawVeriFiOutput):
        return output.claims

    if isinstance(output, dict) and isinstance(output.get("claims"), list):
        claims: List[RawClaim] = []
        for item in output["claims"]:
            try:
                claims.append(RawClaim.model_validate(item))
            except Exception:
                continue
        return claims

    if isinstance(output, str):
        cleaned = output.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and isinstance(parsed.get("claims"), list):
                claims: List[RawClaim] = []
                for item in parsed["claims"]:
                    try:
                        claims.append(RawClaim.model_validate(item))
                    except Exception:
                        continue
                return claims
        except json.JSONDecodeError:
            pass

    if hasattr(output, "claims") and isinstance(getattr(output, "claims"), list):
        claims: List[RawClaim] = []
        for item in getattr(output, "claims"):
            try:
                claims.append(RawClaim.model_validate(item))
            except Exception:
                continue
        return claims

    return []


def map_asset_token(token: str) -> Optional[str]:
    """Map natural-language asset names/synonyms to whitelist tickers."""
    stripped = token.strip()
    normalized = re.sub(r"[^a-zA-ZÇĞİÖŞÜçğıöşü\s]", "", stripped.lower())

    # A bare ticker SYMBOL is only accepted when the source token is written in
    # uppercase (e.g. "USD", "BTC", "COIN", "TRY"). This is critical because several
    # tickers are spelled like ordinary words once lower-cased — COIN/"coin",
    # LINK/"link", DOT/"dot", META/"meta", TRY/"try" — and must NOT be captured from
    # plain prose. Full names / synonyms ("bitcoin", "dolar") are matched separately
    # via alias_map and stay case-insensitive.
    is_symbol_style = stripped.isupper()

    # Accept all whitelist tickers directly (lower-cased lookup key -> canonical ticker).
    ticker_map = {ticker.lower(): ticker for ticker in TOTAL_WHITELIST}

    # Common synonyms and company names for all whitelist groups.
    alias_map = {
        # Fiat currencies
        "dolar": "USD",
        "doları": "USD",
        "dolari": "USD",
        "amerikan doları": "USD",
        "abd doları": "USD",
        "us dollar": "USD",
        "u.s. dollar": "USD",
        "dollar": "USD",
        "dolr": "USD",
        "doller": "USD",
        "dolarrr": "USD",
        "avro": "EUR",
        "euro": "EUR",
        "euor": "EUR",
        "sterlin": "GBP",
        "ingiliz sterlini": "GBP",
        "pound": "GBP",
        "british pound": "GBP",
        "yen": "JPY",
        "japon yeni": "JPY",
        "frank": "CHF",
        "swiss franc": "CHF",
        "isvicre frangi": "CHF",
        "isviçre frangı": "CHF",
        "lira": "TRY",
        "turkish lira": "TRY",
        "turk lirasi": "TRY",
        "türk lirası": "TRY",
        "kanada doları": "CAD",
        "avustralya doları": "AUD",
        "yeni zelanda doları": "NZD",
        "çin yuanı": "CNY",
        "australian dollar": "AUD",
        "canadian dollar": "CAD",
        "new zealand dollar": "NZD",
        "yuan": "CNY",
        "renminbi": "CNY",
        # Crypto
        "bitcoin": "BTC",
        "bitcoın": "BTC",
        "bitcon": "BTC",
        "btcoin": "BTC",
        "ethereum": "ETH",
        "ether": "ETH",
        "etherium": "ETH",
        "etheriyum": "ETH",
        "etheryum": "ETH",
        "ethirium": "ETH",
        "solana": "SOL",
        "solona": "SOL",
        "binance coin": "BNB",
        "bnb coin": "BNB",
        "ripple": "XRP",
        "cardano": "ADA",
        "avalanche": "AVAX",
        "dogecoin": "DOGE",
        "polkadot": "DOT",
        "chainlink": "LINK",
        # Stocks / companies
        "apple": "AAPL",
        "microsoft": "MSFT",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "amazon": "AMZN",
        "nvidia": "NVDA",
        "tesla": "TSLA",
        "meta": "META",
        "netflix": "NFLX",
        "amd": "AMD",
        "intel": "INTC",
        "coinbase": "COIN",
        "paypal": "PYPL",
        "palantir": "PLTR",
        "uber": "UBER",
        "disney": "DIS",
        "walt disney": "DIS",
        "microsof": "MSFT",
        "gogle": "GOOGL",
        "amazn": "AMZN",
        "nvida": "NVDA",
        "tesl": "TSLA",
        "netfliix": "NFLX",
    }

    # 1) Natural-language alias / full name (case-insensitive, always allowed).
    if alias_map.get(normalized) in TOTAL_WHITELIST:
        return alias_map[normalized]

    # 2) Bare ticker symbol — only when written in uppercase in the source text.
    if is_symbol_style and ticker_map.get(normalized) in TOTAL_WHITELIST:
        return ticker_map[normalized]

    # 3) Fuzzy fallback for human typos — restricted to alias/name keys only.
    #    (Fuzzy-matching short ticker symbols is unsafe: "try"->TRY, "dot"->DOT, etc.)
    close = get_close_matches(normalized, list(alias_map.keys()), n=1, cutoff=0.82)
    if close and alias_map.get(close[0]) in TOTAL_WHITELIST:
        return alias_map[close[0]]

    # 4) Multi-token fallback: check each word independently (e.g., "ether fiyatı").
    #    Symbols still require uppercase; names are matched via alias_map.
    raw_parts = stripped.split()
    for raw_part in raw_parts:
        part_norm = re.sub(r"[^a-zA-ZÇĞİÖŞÜçğıöşü]", "", raw_part.lower())
        if alias_map.get(part_norm) in TOTAL_WHITELIST:
            return alias_map[part_norm]
        if raw_part.isupper() and ticker_map.get(part_norm) in TOTAL_WHITELIST:
            return ticker_map[part_norm]
    return None


def extract_deadline(text: str) -> Optional[str]:
    """Extract absolute deadline from Turkish + English time expressions."""
    year_end = extract_year_end_deadline(text)
    if year_end:
        return year_end

    lowered = text.lower()
    if re.search(r"yıl sonu|yıl sonunda|yıl sonuna kadar|yıl sonu itibarıyla|end of year|year[- ]end|by year[- ]end", lowered):
        return f"{now.year}-12-31"
    if "haftaya" in lowered or "next week" in lowered:
        return (now + timedelta(days=7)).strftime("%Y-%m-%d")

    relative = extract_relative_deadline(text)
    if relative:
        return relative

    day_match = re.search(r"(\d+)\s*(gün)\s*(içinde|sonra)|(\d+)\s*(day|days)\s*(in|within|later|after)", lowered)
    if day_match:
        day_val = next((g for g in day_match.groups() if g and g.isdigit()), None)
        if day_val:
            return (now + timedelta(days=int(day_val))).strftime("%Y-%m-%d")

    month_match = re.search(r"(\d+)\s*(ay)\s*(içinde|sonra)|(\d+)\s*(month|months)\s*(in|within|later|after)", lowered)
    if month_match:
        month_val = next((g for g in month_match.groups() if g and g.isdigit()), None)
        if month_val:
            return (now + timedelta(days=int(month_val) * 30)).strftime("%Y-%m-%d")

    year_match = re.search(r"(\d+)\s*(yıl)\s*(içinde|sonra)|(\d+)\s*(year|years)\s*(in|within|later|after)", lowered)
    if year_match:
        year_val = next((g for g in year_match.groups() if g and g.isdigit()), None)
        if year_val:
            return (now + timedelta(days=int(year_val) * 365)).strftime("%Y-%m-%d")

    explicit_year = re.search(r"\b(20\d{2})\b", lowered)
    if explicit_year and re.search(r"başında|sonunda|yıl|end|year", lowered):
        return f"{explicit_year.group(1)}-12-31"
    return None


def _extract_pair_assets(text: str) -> tuple[Optional[str], Optional[str]]:
    pair = re.search(r"([A-Za-zÇĞİÖŞÜçğıöşü]{2,20})\s*/\s*([A-Za-zÇĞİÖŞÜçğıöşü]{2,20})", text)
    if not pair:
        return None, None
    pay = map_asset_token(pair.group(1))
    payda = map_asset_token(pair.group(2))
    return pay, payda


def _extract_last_value(text: str) -> tuple[Optional[float], int]:
    matches = list(re.finditer(r"\d+(?:[.,]\d+)?", text))
    if not matches:
        return None, -1
    last = matches[-1]
    try:
        return float(last.group(0).replace(",", ".")), last.end()
    except ValueError:
        return None, -1


def _extract_value_with_payda(text: str) -> tuple[Optional[float], Optional[str], int]:
    """Extract target value and nearby currency/ticker token."""
    pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*([A-Za-zÇĞİÖŞÜçğıöşü$€₺]{2,12})")
    candidates: list[tuple[float, Optional[str], int]] = []
    for m in pattern.finditer(text):
        raw_num, raw_unit = m.group(1), m.group(2)
        try:
            val = float(raw_num.replace(",", "."))
        except ValueError:
            continue
        unit = map_asset_token(raw_unit)
        candidates.append((val, unit, m.end()))
    if not candidates:
        return None, None, -1
    return candidates[-1]


def _extract_best_numeric_value(text: str) -> tuple[Optional[float], int]:
    """Extract likely target value, avoiding time/year numbers."""
    lowered = text.lower()
    matches = list(re.finditer(r"\d+(?:[.,]\d+)?", text))
    if not matches:
        return None, -1

    time_units = {"gün", "day", "days", "ay", "month", "months", "yıl", "year", "years"}
    filtered: list[re.Match] = []
    for m in matches:
        val_str = m.group(0)
        try:
            val = float(val_str.replace(",", "."))
        except ValueError:
            continue
        tail = lowered[m.end(): m.end() + 15]
        if any(unit in tail for unit in time_units):
            continue
        if 1900 <= val <= 2100 and re.search(r"end|year|yıl|sonu|baş", lowered):
            continue
        filtered.append(m)

    target_match = filtered[-1] if filtered else matches[-1]
    try:
        return float(target_match.group(0).replace(",", ".")), target_match.end()
    except ValueError:
        return None, -1


def _extract_percentage_value(text: str) -> tuple[Optional[float], int]:
    """Extract percentage amount from patterns like %10, 10%, yüzde 10."""
    percent_patterns = [
        r"%\s*(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*%",
        r"y[uü]zde\s*(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*percent",
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


def _resolve_value_from_prompt_or_raw(prompt: str, raw_value: Optional[float]) -> Optional[float]:
    """Prefer clear target value in prompt, fallback to AI-provided value."""
    prompt_value, _ = _extract_best_numeric_value(prompt)
    return prompt_value if prompt_value is not None else raw_value


def _resolve_assets_from_prompt_or_raw(
    prompt: str, raw_pay: Optional[str], raw_payda: Optional[str], value_end: int
) -> tuple[Optional[str], Optional[str]]:
    """Use prompt evidence first, then AI hints, then heuristics."""
    pair_pay, pair_payda = _extract_pair_assets(prompt)
    if pair_pay and pair_payda:
        return pair_pay, pair_payda

    pay = map_asset_token(raw_pay or "") if raw_pay else None
    payda = map_asset_token(raw_payda or "") if raw_payda else None

    prompt_primary = _extract_primary_asset(prompt)
    if prompt_primary:
        pay = prompt_primary

    if not payda:
        payda = _extract_payda_near_value(prompt, value_end, pay)

    # If AI inverted pair (e.g. pay=USD, payda=NVDA), fix by prompt primary asset.
    if pay and payda and pay in CURRENCIES and payda in STOCKS + CRYPTO and prompt_primary in STOCKS + CRYPTO:
        pay, payda = prompt_primary, pay

    return pay, payda


def normalize_raw_claim(raw_claim: RawClaim, prompt: str) -> Optional[FinancialClaim]:
    """Convert permissive AI output into strict final schema."""
    value_type = _detect_value_type(prompt, raw_claim.value_type)
    if value_type in {"PERCENTAGE_UP", "PERCENTAGE_DOWN"}:
        value, value_end = _extract_percentage_value(prompt)
    else:
        value = _resolve_value_from_prompt_or_raw(prompt, raw_claim.value)
        _, value_end = _extract_best_numeric_value(prompt)
    if value is None:
        return None

    value_with_unit, unit_payda, value_end = _extract_value_with_payda(prompt)
    if value_with_unit is not None and value_type == "PRICE":
        value = value_with_unit
    pay, payda = _resolve_assets_from_prompt_or_raw(prompt, raw_claim.pay, raw_claim.payda, value_end)
    if not payda and unit_payda and unit_payda != pay:
        payda = unit_payda
    if value_type in {"PERCENTAGE_UP", "PERCENTAGE_DOWN"} and not payda:
        payda = _extract_base_payda_from_text(prompt)
    if not pay:
        return None

    deadline = extract_deadline(prompt) or raw_claim.deadline
    status = "HARD_CLAIM" if (pay is not None and payda is not None and value is not None and deadline is not None) else "POSSIBLE_CLAIM"

    try:
        return FinancialClaim(
            pay=pay,
            payda=payda,
            value=float(value),
            value_type=value_type,
            deadline=deadline,
            status=status,
        )
    except Exception:
        return None


def rule_based_claims_from_prompt(prompt: str) -> List[FinancialClaim]:
    """Deterministic fallback extraction for common financial claim patterns."""
    text = prompt.strip()
    deadline = extract_deadline(text)
    value_type = _detect_value_type(text, None)
    pay, payda = _extract_pair_assets(text)

    if value_type in {"PERCENTAGE_UP", "PERCENTAGE_DOWN"}:
        value, value_end = _extract_percentage_value(text)
        unit_payda = None
    else:
        value, unit_payda, value_end = _extract_value_with_payda(text)
    if value is None:
        value, value_end = _extract_best_numeric_value(text)
    if value is None:
        return []

    if not pay:
        pay = _extract_primary_asset(text)
    if not pay:
        return []

    if not payda:
        payda = _extract_payda_near_value(text, value_end, pay)
    if not payda and unit_payda and unit_payda != pay:
        payda = unit_payda
    if value_type in {"PERCENTAGE_UP", "PERCENTAGE_DOWN"} and not payda:
        payda = _extract_base_payda_from_text(text)

    status = "HARD_CLAIM" if (pay is not None and payda is not None and value is not None and deadline is not None) else "POSSIBLE_CLAIM"
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


def analyze_prompt_to_claims(prompt: str) -> List[FinancialClaim]:
    """AI-first extraction, then strict normalization, then regex fallback."""
    try:
        strict_response = verifi_agent.run(prompt, response_model=VeriFiOutput)
        strict_output = getattr(strict_response, "content", strict_response)
        strict_claims = extract_claims(strict_output)
    except Exception:
        strict_claims = []
    if strict_claims:
        normalized: List[FinancialClaim] = []
        for claim in strict_claims:
            normalized_claim = normalize_raw_claim(
                RawClaim(
                    pay=claim.pay,
                    payda=claim.payda,
                    value=claim.value,
                    value_type=claim.value_type,
                    deadline=claim.deadline,
                    status=claim.status,
                ),
                prompt,
            )
            if normalized_claim:
                normalized.append(normalized_claim)
        if normalized:
            return normalized

    try:
        raw_response = raw_verifi_agent.run(prompt, response_model=RawVeriFiOutput)
        raw_output = getattr(raw_response, "content", raw_response)
        raw_claims = extract_raw_claims(raw_output)
    except Exception:
        raw_claims = []

    normalized: List[FinancialClaim] = []
    for raw_claim in raw_claims:
        claim = normalize_raw_claim(raw_claim, prompt)
        if claim:
            normalized.append(claim)
    if normalized:
        return normalized

    return rule_based_claims_from_prompt(prompt)


def run_verifi(prompt: str):
    """Run agent, then write one claim per line with Python formatting."""
    claims = analyze_prompt_to_claims(prompt)
    extracted_deadline = extract_deadline(prompt)

    with open("test_results.txt", "w", encoding="utf-8") as f:
        if not claims:
            f.write("No valid claims extracted.\n")
            return None

        for idx, claim in enumerate(claims, start=1):
            deadline = extracted_deadline or claim.deadline
            line = (
                f"{idx}. pay={claim.pay} | payda={claim.payda or 'null'} | "
                f"value={claim.value} | value_type={claim.value_type} | "
                f"deadline={deadline or 'null'} | status={claim.status}"
            )
            f.write(line + "\n")

    return claims


def run_test_cases(test_cases: List[str], output_file: str = "test_results.txt"):
    """Run multiple prompts and write all outputs into one file."""
    total = len(test_cases)
    with open(output_file, "w", encoding="utf-8") as f:
        for case_idx, prompt in enumerate(test_cases, start=1):
            extracted_deadline = extract_deadline(prompt)
            claims = analyze_prompt_to_claims(prompt)

            f.write(f"[{case_idx}] INPUT: {prompt}\n")
            if not claims:
                f.write("No valid claims extracted.\n\n")
                remaining = total - case_idx
                print(f"[{case_idx}/{total}] analyzed | remaining: {remaining}")
                continue

            for claim_idx, claim in enumerate(claims, start=1):
                deadline = extracted_deadline or claim.deadline
                line = (
                    f"{claim_idx}. pay={claim.pay} | payda={claim.payda or 'null'} | "
                    f"value={claim.value} | value_type={claim.value_type} | "
                    f"deadline={deadline or 'null'} | status={claim.status}"
                )
                f.write(line + "\n")
            f.write("\n")
            remaining = total - case_idx
            print(f"[{case_idx}/{total}] analyzed | remaining: {remaining}")


if __name__ == "__main__":
    def to_multisentence_inputs(claims: List[str], lang: str) -> List[str]:
        """Wrap claim text with realistic extra context (>=3 sentences)."""
        if lang == "tr":
            return [
                (
                    "Sabah ekip toplantısında önce ürün yol haritasını konuştuk. "
                    f"Sonra piyasaya dair görüşümü paylaştım: {claim} "
                    "Yine de risk yönetimi için pozisyonu kademeli açmayı planlıyorum."
                )
                for claim in claims
            ]
        return [
            (
                "In the morning sync we first reviewed product milestones. "
                f"Then I shared one market view: {claim} "
                "Even so, I would size positions gradually because volatility is still high."
            )
            for claim in claims
        ]

    price_claims_tr = [
        "Bitcoin kısa vadede 103000 dolar olur.",
        "Etheriyum orta vadede 6200 dollar olur.",
        "Solana yıl sonunda 320 USD olur.",
        "Binance coin kısa vadede 860 dolar olur.",
        "Apple hissesi orta vadede 290 dolar olur.",
        "Microsof yıl sonunda 640 dolar olur.",
        "Gogle kısa vadede 260 dollar olur.",
        "Amazn orta vadede 275 dolar olur.",
        "Nvida yıl sonunda 1400 USD olur.",
        "Tesl haftaya 360 dolar olur.",
        "Meta hissesi orta vadede 780 USD olur.",
        "Netfliix yıl sonunda 930 dollar olur.",
        "USD/TRY orta vadede 49.10 olur.",
        "EUR/USD kısa vadede 1.22 olur.",
        "GBP/USD yıl sonunda 1.45 olur.",
    ]
    price_claims_en = [
        "Bitcoin will reach 110000 dollars in the short term.",
        "Etherium will hit 6800 doller in the medium term.",
        "Solana will be 360 USD by year-end.",
        "Binance coin will be 920 dollars in the short term.",
        "Apple stock will be 305 dollars in the medium term.",
        "Microsof will be 670 dollars by year-end.",
        "Gogle will hit 270 dollars in the short term.",
        "Amazn will reach 285 dollars in the medium term.",
        "Nvida will be 1450 dollars by year-end.",
        "Tesl will be 375 dollars next week.",
        "Meta will be 820 USD in the medium term.",
        "Netflix will hit 960 USD by year-end.",
        "USD/JPY will test 170 in the short term.",
        "AUD/USD will be 0.79 in the medium term.",
        "CNY/TRY will be 7.60 by year-end.",
    ]
    price_claims = to_multisentence_inputs(price_claims_tr, "tr") + to_multisentence_inputs(price_claims_en, "en")

    percent_claims_tr = [
        "Bitcoin doler bazında yıl sonunda %12 artacak.",
        "Etheriyum dolar karşısında orta vadede yüzde 9 yükselecek.",
        "Solana BTC bazında kısa vadede %7 düşecek.",
        "Binance coin lira karşısında yıl sonunda yüzde 15 değer kazanacak.",
        "XRP USD bazında kısa vadede %6 artış gösterecek.",
        "ADA EUR karşısında orta vadede yüzde 4 azalış yaşayacak.",
        "AVAX dolar bazında haftaya %5 yükselecek.",
        "DOGE BTC karşısında kısa vadede yüzde 11 düşecek.",
        "DOT USD bazında yıl sonunda %8 artacak.",
        "LINK TRY karşısında orta vadede yüzde 10 değer kazanacak.",
        "Apple dolar bazında yıl sonunda %13 artacak.",
        "Microsof avro karşısında kısa vadede yüzde 3 düşecek.",
        "Gogle dolar bazında orta vadede %5 artış yaşayacak.",
        "Amazn lira karşısında yıl sonunda yüzde 14 yükselecek.",
        "Nvida dolar bazında kısa vadede %9 düşecek.",
    ]
    percent_claims_en = [
        "Bitcoin will rise by 12% against USD by year-end.",
        "Etheriyum will increase 8 percent versus dollar in the medium term.",
        "Solana will drop 6% against BTC in the short term.",
        "Binance coin will gain 14% against lira by year-end.",
        "XRP will increase 5% versus USD next week.",
        "ADA will fall 4 percent against EUR in the medium term.",
        "AVAX will rise 7% against USD in the short term.",
        "DOGE will drop 10% versus BTC by year-end.",
        "DOT will gain 9% against USD in the medium term.",
        "LINK will increase 11 percent against TRY in the short term.",
        "Apple will rise 6% against dollar by year-end.",
        "Microsof will decline 3% versus euro in the short term.",
        "Gogle will gain 4 percent against dollar in the medium term.",
        "Amazn will rise 8% against lira by year-end.",
        "Nvida will drop 5% versus dollar in the short term.",
    ]
    percent_claims = to_multisentence_inputs(percent_claims_tr, "tr") + to_multisentence_inputs(percent_claims_en, "en")

    possible_percentage_tr = [
        "Bitcoin %10 artacak.",
        "Etheriyum yüzde 8 düşecek.",
        "Apple %6 yükselecek.",
        "Gogle yüzde 5 azalır.",
        "Nvida %9 artış yaşayacak.",
        "Dolar %4 değer kazanacak.",
        "Avro yüzde 3 düşecek.",
        "Solana %12 yükselecek.",
    ]
    possible_percentage_en = [
        "Bitcoin will rise 10%.",
        "Etherium will drop 7 percent.",
        "Apple will gain 6%.",
        "Gogle will decline 5 percent.",
        "Nvida will increase 9%.",
        "Dollar will rise 4%.",
        "Euro will fall 3 percent.",
    ]
    possible_percentage_claims = to_multisentence_inputs(possible_percentage_tr, "tr") + to_multisentence_inputs(possible_percentage_en, "en")

    possible_price_tr = [
        "Solana 420 USD olacak.",
        "BNB 980 olacak.",
        "Microsof 720 bandını test eder.",
        "Amazn 310 dolar görür.",
        "Tesl 450 olur.",
        "Bitcoin 125000 olur.",
        "Etheriyum 7500 dolar olur.",
        "Apple 340 olur.",
    ]
    possible_price_en = [
        "Solana will be 420.",
        "BNB will hit 980 USD.",
        "Microsof will test 720.",
        "Amazn reaches 310 dollars.",
        "Tesl will be 450.",
        "Bitcoin will be 125000.",
        "Etherium will be 7500 dollars.",
    ]
    possible_price_claims = to_multisentence_inputs(possible_price_tr, "tr") + to_multisentence_inputs(possible_price_en, "en")

    noise_cases = [
        "Sabah erkenden yürüyüşe çıktım. Ofise dönünce e-postaları yanıtladım. Akşam da arkadaşlarımla buluştum.",
        "Bugün sadece tasarım revizyonlarını konuştuk. Ürün metinlerinde dil birliği eksikti. Yarın tekrar gözden geçireceğiz.",
        "Toplantı beklenenden kısa sürdü. Herkes görev listesini güncelledi. Sonra sprint planını kapattık.",
        "The weather was cloudy in the morning. I spent the afternoon fixing documentation typos. Tonight I will read a novel.",
        "We discussed onboarding friction in user interviews. The team proposed three UX changes. Final decisions will be made tomorrow.",
        "Yeni kahve makinesi sonunda geldi. Mutfakta küçük bir düzenleme yaptık. Herkes öğleden sonra daha enerjikti.",
        "I reviewed pull requests for two hours. Then I prepared release notes for the mobile app. Nothing else happened today.",
        "Hafta sonu için gezi planı yaptık. Otel rezervasyonunu tamamladık. Yolculuk listesini de hazırladık.",
        "The design team requested new icon variants. Marketing asked for copy tweaks on the homepage. Support also shared user feedback.",
        "Ofiste internet bir süre yavaştı. Teknik ekip modemleri yeniden başlattı. Akşam üstü bağlantı normale döndü.",
    ]

    test_cases = price_claims + percent_claims + possible_percentage_claims + possible_price_claims + noise_cases

    if len(test_cases) != 100:
        raise ValueError(f"Expected 100 test cases, got {len(test_cases)}")
    try:
        run_test_cases(test_cases, output_file="test_results.txt")
        print("100 test case sonucu test_results.txt dosyasına yazıldı.")
    except Exception as e:
        print(f"Hata: {e}")
