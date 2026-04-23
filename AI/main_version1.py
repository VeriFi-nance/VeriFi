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
        "Bitcoin kısa vadede 95000 USD olur.",
        "Apple hisseleri yıl sonunda 250 USD seviyesine ulaşır.",
        "USD/TRY paritesi orta vadede 45.50 seviyesini görecek.",
        "Ethereum haftaya 4200 USD bandını geçer.",
        "Tesla orta vadede 300 USD hedef fiyatına sahip.",
        "Dolar kuru yıl sonu itibarıyla 42 TRY olacaktır.",
        "NVDA için kısa vadeli beklentim 950 USD.",
        "SOL/USD paritesi 3 ay içinde 200 değerine ulaşır.",
        "Microsoft 2026 sonunda 500 USD olur.",
        "Avax kısa vadede 60 USD hedefliyor.",
        "Google hissesi orta vadede 180 USD bandına yerleşir.",
        "GBP/USD paritesi yıl sonunda 1.35 seviyesini test eder.",
        "BTC 2027 başında 150000 USD olur.",
        "Amazon kısa vadede 210 USD seviyesine çıkar.",
        "Meta orta vadede 600 USD hedef fiyatla izlenmeli.",
        "Netflix yıl sonuna kadar 700 USD olur.",
        "Doge kısa vadede 0.50 USD seviyesini aşar.",
        "XRP orta vadede 2 USD bandına oturur.",
        "AMD hissesi haftaya 200 USD olur.",
        "Intel kısa vadede 45 USD hedefliyor.",
        "Coinbase orta vadede 300 USD olur.",
        "Paypal yıl sonunda 85 USD seviyesine gelir.",
        "Palantir kısa vadede 35 USD olur.",
        "Uber orta vadede 90 USD seviyesini görür.",
        "Disney yıl sonuna kadar 130 USD olur.",
        "BTC/EUR paritesi haftaya 85000 seviyesini aşar.",
        "ETH/TRY orta vadede 150000 bandına gelir.",
        "Link kısa vadede 25 USD olur.",
        "Dot yıl sonunda 15 USD seviyesine çıkar.",
        "Ada orta vadede 1.20 USD olur.",
        "Dolar/Frank paritesi kısa vadede 0.90 CHF olur.",
        "Yen orta vadede 155 JPY/USD seviyesini görür.",
        "CNY/TRY paritesi yıl sonunda 6.50 olur.",
        "AUD/USD kısa vadede 0.70 bandına yerleşir.",
        "CAD orta vadede 1.40 USD olur.",
        "NZD/USD yıl sonunda 0.65 seviyesine gelir.",
        "XRP/TRY kısa vadede 35 seviyesini aşar.",
        "Solana yıl sonunda 250 USD olur.",
        "BNB kısa vadede 700 USD hedefliyor.",
        "AVAX yıl sonunda 120 USD olur.",
    ]

    en_hard_claims = [
        "Bitcoin will reach 98000 USD in the short term.",
        "Apple stock will hit 260 USD by year-end.",
        "USD/TRY will test 46.20 in the medium term.",
        "Ethereum will move above 4300 USD next week.",
        "Tesla has a medium-term target of 320 USD.",
        "The dollar rate will be 43 TRY by the end of the year.",
        "NVDA is expected to reach 980 USD in the short term.",
        "SOL/USD will reach 210 within 3 months.",
        "Microsoft will be 520 USD by end of 2026.",
        "AVAX targets 70 USD in the short term.",
        "Google stock settles at 185 USD in the medium term.",
        "GBP/USD will test 1.37 by year-end.",
        "BTC will be 155000 USD at the beginning of 2027.",
        "Amazon rises to 215 USD in the short term.",
        "Meta should be tracked with a 620 USD medium-term target.",
        "Netflix reaches 720 USD by the end of the year.",
        "DOGE will break 0.55 USD in the short term.",
        "XRP stabilizes around 2.2 USD in the medium term.",
        "AMD will be 210 USD next week.",
        "Intel targets 48 USD in the short term.",
        "Coinbase reaches 320 USD in the medium term.",
        "PayPal will be 88 USD by year-end.",
        "Palantir reaches 38 USD in the short term.",
        "Uber sees 95 USD in the medium term.",
        "Disney will be 135 USD by end of year.",
        "BTC/EUR will cross 87000 next week.",
        "ETH/TRY reaches 160000 in the medium term.",
        "LINK will be 27 USD in the short term.",
        "DOT climbs to 16 USD by year-end.",
        "ADA will be 1.30 USD in the medium term.",
        "USD/CHF reaches 0.92 in the short term.",
        "JPY/USD will see 0.0068 in the medium term.",
        "CNY/TRY reaches 6.8 by year-end.",
        "AUD/USD settles at 0.72 in the short term.",
        "CAD will be 1.45 USD in the medium term.",
        "NZD/USD reaches 0.67 by year-end.",
        "XRP/TRY crosses 38 in the short term.",
        "Solana reaches 270 USD by year-end.",
        "BNB targets 760 USD in the short term.",
        "USD/JPY will exceed 162 by year-end.",
    ]

    tr_possible_claims = [
        "Bitcoin 100000 olacak.",
        "Apple hissesi kısa vadede 300 bandına çıkar.",
        "Dolar yıl sonunda 50 bandını geçer.",
        "Ethereum 5000 USD hedefliyor.",
        "Tesla 400 doları görecek.",
        "Solana haftaya 300 olur.",
        "NVDA 1200 USD seviyesine gelir.",
        "Microsoft orta vadede 600 seviyesini test eder.",
        "BTC 120000 patates olur.",
        "Doge 1 olur.",
    ]

    en_possible_claims = [
        "Bitcoin will be 110000.",
        "Apple stock moves to 310 in the short term.",
        "Dollar will pass 52 by year-end.",
        "Ethereum targets 5200 USD.",
        "Tesla will see 420 dollars.",
        "Solana will be 320 next week.",
        "NVDA reaches 1250 USD.",
        "Microsoft tests 650 in the medium term.",
        "BTC goes to 130000 potatoes.",
        "DOGE will be 1.2.",
    ]

    test_cases = tr_hard_claims + en_hard_claims + tr_possible_claims + en_possible_claims

    if len(test_cases) != 100:
        raise ValueError(f"Expected 100 test cases, got {len(test_cases)}")
    try:
        run_test_cases(test_cases, output_file="test_results.txt")
        print("100 test case sonucu test_results.txt dosyasına yazıldı.")
    except Exception as e:
        print(f"Hata: {e}")