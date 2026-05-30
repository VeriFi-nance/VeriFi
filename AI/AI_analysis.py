"""LLM-based financial claim extraction.

This module wraps the agno agents (OpenAI or local LM Studio) and converts their
output into the strict `FinancialClaim` schema. It can be used on its own:

    from AI_analysis import analyze_with_ai
    claims = analyze_with_ai("Bitcoin kısa vadede 103000 dolar olur.")

The strict data model, asset whitelist and the deterministic regex helpers used
during normalization are imported from `RegEx_analysis` so the two layers stay in
sync and we never duplicate the mapping rules.
"""

from typing import Optional, List
import os
import json
from pydantic import BaseModel
from agno.agent import Agent
from agno.models.openai import OpenAIChat

from RegEx_analysis import (
    TOTAL_WHITELIST,
    CURRENCIES,
    CRYPTO,
    STOCKS,
    today_str,
    FinancialClaim,
    map_asset_token,
    extract_deadline,
    passes_prefilter,
    _extract_pair_assets,
    _extract_value_with_payda,
    _extract_best_numeric_value,
    _extract_percentage_value,
    _detect_value_type,
    _extract_base_payda_from_text,
    _extract_primary_asset,
    _extract_payda_near_value,
)


# ---------------------------------------------------------------------------
# Permissive AI output schemas (Python enforces the final strict format).
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Agent configuration
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Output normalization
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Main entry point (AI-only)
# ---------------------------------------------------------------------------
def analyze_with_ai(prompt: str) -> List[FinancialClaim]:
    """AI extraction (strict agent, then permissive agent) + strict normalization.

    Returns an empty list when the pre-filter rejects the text or when neither
    agent produces a usable claim. This function does NOT fall back to the regex
    extractor — orchestration lives in `General_analysis.py`.
    """
    # Pre-AI gate: drop obvious non-claims before incurring any model call.
    if not passes_prefilter(prompt):
        return []

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
    return normalized


if __name__ == "__main__":
    samples = [
        "Bitcoin kısa vadede 103000 dolar olur.",
        "Apple dolar bazında yıl sonunda %13 artacak.",
    ]
    for s in samples:
        print(f"INPUT: {s}")
        for c in analyze_with_ai(s):
            print(f"  -> pay={c.pay} payda={c.payda} value={c.value} type={c.value_type} deadline={c.deadline} status={c.status}")
        print()
