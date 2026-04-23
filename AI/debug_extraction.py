#!/usr/bin/env python3
"""Debug extraction with identical flow to new_main.py"""

import os
import json
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from schema import HardClaimExtractor, VALID_ASSETS
from datetime import datetime

local_llm = OpenAIChat(
    id="ministral-3-8b-instruct-2512",
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

def get_verifi_instructions():
    now = datetime.now()
    current_year = now.year
    
    return f"""ROLE: You are VeriFi's Financial Claim Extractor. Extract ONLY verifiable, concrete financial claims from text.

REQUIRED FIELDS FOR EACH CLAIM:
- base_asset (string): Main asset (USD, BTC, EUR, etc.)
- quote_asset (string): Counter asset (TRY, USD, etc.) 
- amount (float): Numerical target value
- unit (string): "price" for absolute values or "percentage" for % changes
- time_frame (string): Time period from text (e.g., "end of 2026", "Q4", "by year-end")
- status (string): "verified_claim" if time_frame exists, else "possible_claim"

VALID ASSETS: {', '.join(VALID_ASSETS)}

EXTRACTION RULES:
1. Extract ONLY from this valid asset list. Reject anything else.
2. REQUIRE numerical value + time period to extract (if no time period, status="possible_claim").
3. Emotional language WITHOUT numbers ("will moon", "crash soon") = SKIP.
4. One sentence = potentially multiple claims if multiple assets mentioned.
5. For "USD moves to 44 TRY by end 2026": base=USD, quote=TRY, amount=44, unit=price, time_frame="end of 2026"
6. For "BTC +10% in Q4": base=BTC, quote=USD, amount=10, unit=percentage, time_frame="Q4"

OUTPUT: Return ONLY valid JSON. No explanations, no markdown, no extra text.
JSON must start with {{ and end with }}. 
Response format:
{{
  "claims": [
    {{"base_asset": "USD", "quote_asset": "TRY", "amount": 44, "unit": "price", "time_frame": "end of 2026", "status": "verified_claim"}},
    {{"base_asset": "EUR", "quote_asset": "TRY", "amount": 48, "unit": "price", "time_frame": "late 2026", "status": "verified_claim"}}
  ]
}}

If NO valid claims exist in input, return: {{"claims": []}}
"""

def extract_json_from_text(text):
    """Extract valid JSON object from text that may contain extra content."""
    if not text:
        return None
    
    print(f"[DEBUG] Raw text: {text[:100]}...")
    
    # Remove markdown code fences if present
    text = text.replace('```json', '').replace('```', '')
    
    print(f"[DEBUG] After markdown removal: {text[:100]}...")
    
    # Try to find JSON block
    start = text.find('{')
    end = text.rfind('}') + 1
    
    if start == -1 or end == 0:
        print(f"[DEBUG] No JSON block found")
        return None
    
    json_str = text[start:end]
    print(f"[DEBUG] Extracted JSON string: {json_str[:100]}...")
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[DEBUG] JSONDecodeError: {e}")
        # Try to repair common JSON issues
        try:
            # Replace single quotes with double quotes
            json_str_fixed = json_str.replace("'", '"')
            return json.loads(json_str_fixed)
        except:
            return None

verifi_agent = Agent(
    model=local_llm,
    instructions=get_verifi_instructions(),
    markdown=False
)

line = "We expect USD to move toward 44 TRY by the end of 2026."
print(f"Testing with: {line}\n")

response = verifi_agent.run(line, response_model=HardClaimExtractor)

print(f"Response type: {type(response)}")
print(f"Response.content type: {type(response.content)}\n")

extraction = getattr(response, 'content', response) if response else None
print(f"Extraction value:\n{extraction}\n")

parsed = extract_json_from_text(extraction)
print(f"\nParsed result: {parsed}")

if parsed:
    claims_list = parsed.get('claims', [])
    print(f"Claims count: {len(claims_list)}")
    for c in claims_list:
        print(f"  Claim: {c}")
