from datetime import datetime, timedelta
from typing import Optional, List
import os
import re
import json
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
        "4. If payda is outside whitelist, set payda=null and status='POSSIBLE_CLAIM'.",
        "5. Return only schema fields. Never include timeframe.",
    ],
)

# Secondary AI extractor: permissive schema, then Python enforces final format.
raw_verifi_agent = Agent(
    model=build_model(),
    markdown=False,
    instructions=[
        f"Today date: {today_str}.",
        "Extract financial claims from Turkish or English text.",
        "Return ONLY JSON with this shape: {'claims':[{'pay':..., 'payda':..., 'value':..., 'deadline':..., 'status':...}]}",
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
    normalized = re.sub(r"[^a-zA-ZÇĞİÖŞÜçğıöşü\s]", "", token.strip().lower())
    upper = token.strip().upper()

    # Accept all whitelist tickers directly.
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
        "avro": "EUR",
        "euro": "EUR",
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
        "ethereum": "ETH",
        "solana": "SOL",
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
    }

    mapped = ticker_map.get(normalized) or alias_map.get(normalized) or upper
    return mapped if mapped in TOTAL_WHITELIST else None


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


def _extract_primary_asset(text: str) -> Optional[str]:
    tokens = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", text)
    # First check unigrams then bigrams/trigrams for aliases like "us dollar".
    for n in (1, 2, 3):
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
    value = _resolve_value_from_prompt_or_raw(prompt, raw_claim.value)
    if value is None:
        return None

    value_with_unit, unit_payda, value_end = _extract_value_with_payda(prompt)
    if value_with_unit is not None:
        value = value_with_unit
    pay, payda = _resolve_assets_from_prompt_or_raw(prompt, raw_claim.pay, raw_claim.payda, value_end)
    if not payda and unit_payda and unit_payda != pay:
        payda = unit_payda
    if not pay:
        return None

    deadline = extract_deadline(prompt) or raw_claim.deadline
    status = "HARD_CLAIM" if deadline and payda else "POSSIBLE_CLAIM"

    try:
        return FinancialClaim(
            pay=pay,
            payda=payda,
            value=float(value),
            deadline=deadline,
            status=status,
        )
    except Exception:
        return None


def rule_based_claims_from_prompt(prompt: str) -> List[FinancialClaim]:
    """Deterministic fallback extraction for common financial claim patterns."""
    text = prompt.strip()
    deadline = extract_deadline(text)
    pay, payda = _extract_pair_assets(text)

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

    status = "HARD_CLAIM" if deadline and payda else "POSSIBLE_CLAIM"
    return [
        FinancialClaim(
            pay=pay,
            payda=payda,
            value=value,
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
                f"value={claim.value} | deadline={deadline or 'null'} | status={claim.status}"
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
                    f"value={claim.value} | deadline={deadline or 'null'} | status={claim.status}"
                )
                f.write(line + "\n")
            f.write("\n")
            remaining = total - case_idx
            print(f"[{case_idx}/{total}] analyzed | remaining: {remaining}")


if __name__ == "__main__":
    tr_hard_claims = [
        "Bitcoin kısa vadede 102000 USD seviyesini görür.",
        "Ethereum orta vadede 6100 USD olur.",
        "Solana yıl sonunda 310 USD olur.",
        "BNB kısa vadede 840 USD hedefler.",
        "XRP orta vadede 2.8 USD bandına gelir.",
        "ADA yıl sonunda 2.4 USD olur.",
        "AVAX kısa vadede 145 USD olur.",
        "DOGE haftaya 0.62 USD seviyesini test eder.",
        "DOT orta vadede 24 USD olur.",
        "LINK yıl sonunda 42 USD seviyesine çıkar.",
        "AAPL kısa vadede 275 USD olur.",
        "MSFT orta vadede 610 USD hedefler.",
        "GOOGL yıl sonunda 245 USD olur.",
        "AMZN kısa vadede 255 USD seviyesine gelir.",
        "NVDA yıl sonunda 1320 USD olur.",
        "TSLA haftaya 335 USD olur.",
        "META orta vadede 720 USD hedefler.",
        "NFLX yıl sonuna kadar 860 USD olur.",
        "AMD kısa vadede 245 USD olur.",
        "INTC orta vadede 63 USD olur.",
        "COIN yıl sonunda 410 USD seviyesine çıkar.",
        "PYPL kısa vadede 115 USD olur.",
        "PLTR orta vadede 58 USD hedefliyor.",
        "UBER yıl sonunda 122 USD olur.",
        "DIS kısa vadede 165 USD seviyesini görür.",
        "USD/TRY orta vadede 47.20 olur.",
        "EUR/USD kısa vadede 1.18 bandına gelir.",
        "GBP/USD yıl sonunda 1.40 olur.",
        "USD/JPY kısa vadede 166 seviyesine çıkar.",
        "CHF/TRY orta vadede 56 olur.",
        "AUD/USD yıl sonunda 0.75 olur.",
        "CAD/USD kısa vadede 0.78 olur.",
        "NZD/USD orta vadede 0.71 olur.",
        "CNY/TRY yıl sonunda 7.30 olur.",
        "BTC/TRY kısa vadede 5600000 olur.",
        "ETH/TRY orta vadede 190000 olur.",
        "AAPL/TRY yıl sonunda 11800 olur.",
        "TSLA/TRY kısa vadede 14500 olur.",
        "NVDA/USD orta vadede 1280 olur.",
        "GOOGL/TRY yıl sonunda 8600 olur.",
    ]

    en_hard_claims = [
        "Bitcoin will reach 108000 USD in the short term.",
        "Ethereum will hit 6400 USD in the medium term.",
        "Solana will be 340 USD by year-end.",
        "BNB is expected to reach 890 USD in the short term.",
        "XRP will stabilize at 3.1 USD in the medium term.",
        "ADA will rise to 2.6 USD by year-end.",
        "AVAX will be 155 USD in the short term.",
        "DOGE will move to 0.68 USD next week.",
        "DOT will test 26 USD in the medium term.",
        "LINK will be 46 USD by year-end.",
        "Apple stock will be 285 USD in the short term.",
        "Microsoft targets 635 USD in the medium term.",
        "Google will reach 255 USD by year-end.",
        "Amazon will hit 268 USD in the short term.",
        "NVIDIA will be 1380 USD by year-end.",
        "Tesla will be 350 USD next week.",
        "Meta will reach 760 USD in the medium term.",
        "Netflix will hit 900 USD by the end of the year.",
        "AMD will be 260 USD in the short term.",
        "Intel will reach 66 USD in the medium term.",
        "Coinbase will be 430 USD by year-end.",
        "PayPal will reach 124 USD in the short term.",
        "Palantir will be 62 USD in the medium term.",
        "Uber will hit 128 USD by year-end.",
        "Disney will reach 172 USD in the short term.",
        "USD/TRY will test 48.10 in the medium term.",
        "EUR/USD will move to 1.20 in the short term.",
        "GBP/USD will be 1.42 by year-end.",
        "USD/JPY will reach 168 in the short term.",
        "CHF/TRY will hit 58 in the medium term.",
        "AUD/USD will be 0.77 by year-end.",
        "CAD/USD will be 0.80 in the short term.",
        "NZD/USD will test 0.73 in the medium term.",
        "CNY/TRY will be 7.45 by year-end.",
        "BTC/TRY will reach 5900000 in the short term.",
        "ETH/TRY will be 205000 in the medium term.",
        "AAPL/TRY will hit 12500 by year-end.",
        "TSLA/TRY will be 15500 in the short term.",
        "NVDA/USD will test 1340 in the medium term.",
        "GOOGL/TRY will be 9100 by year-end.",
    ]

    tr_possible_claims = [
        "Bitcoin 115000 olacak.",
        "Apple hissesi 340 bandına çıkar.",
        "Dolar 54 bandını geçer.",
        "Ethereum 7000 USD hedefliyor.",
        "Tesla 480 doları görecek.",
        "Solana 380 olur.",
        "NVDA 1500 USD seviyesine gelir.",
        "Microsoft 700 seviyesini test eder.",
        "BTC 140000 patates olur.",
        "Doge 1.4 olur.",
    ]

    en_possible_claims = [
        "Bitcoin will be 118000.",
        "Apple stock moves to 355.",
        "Dollar will pass 56.",
        "Ethereum targets 7300 USD.",
        "Tesla will see 500 dollars.",
        "Solana will be 390.",
        "NVDA reaches 1580 USD.",
        "Microsoft tests 730.",
        "BTC goes to 145000 potatoes.",
        "DOGE will be 1.5.",
    ]

    noise_cases = [
        "Bugun hava kapali, kahve icip yuruyuse cikacagim.",
        "Toplantiyi yarin sabah dokuzda baslatalim.",
        "The movie was great and the soundtrack was amazing.",
        "Please send me the design draft before lunch.",
        "Kedim bu sabah koltukta uyuyakaldi.",
        "We should refactor the login page styles this sprint.",
        "Hafta sonu ailece piknige gidecegiz.",
        "The server room door was left open yesterday.",
        "Yeni ofis bitkileri ortama cok iyi geldi.",
        "Can you review the onboarding copy for grammar?",
    ]

    test_cases = tr_hard_claims + en_hard_claims + tr_possible_claims + en_possible_claims + noise_cases

    if len(test_cases) != 110:
        raise ValueError(f"Expected 110 test cases, got {len(test_cases)}")
    try:
        run_test_cases(test_cases, output_file="test_results.txt")
        print("110 test case sonucu test_results.txt dosyasına yazıldı.")
    except Exception as e:
        print(f"Hata: {e}")