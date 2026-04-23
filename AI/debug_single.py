#!/usr/bin/env python3
"""Debug script to see raw LLM output for a single line."""

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

agent = Agent(
    model=local_llm,
    instructions=get_verifi_instructions(),
    markdown=False
)

test_line = "We expect USD to move toward 44 TRY by the end of 2026."
print(f"Input: {test_line}\n")

response = agent.run(test_line, response_model=HardClaimExtractor)
print(f"Response type: {type(response)}")
print(f"Response attributes: {dir(response)}")
print(f"\nResponse.content type: {type(response.content)}")
print(f"Response.content value:\n{response.content}\n")

# Try to parse
content = response.content
if isinstance(content, str):
    print("Content is string. Attempting JSON parse...")
    start = content.find('{')
    end = content.rfind('}') + 1
    if start != -1 and end != 0:
        json_str = content[start:end]
        print(f"Extracted JSON:\n{json_str}\n")
        try:
            parsed = json.loads(json_str)
            print(f"Parsed successfully:\n{json.dumps(parsed, indent=2)}")
        except Exception as e:
            print(f"Parse error: {e}")
else:
    print(f"Content is object: {content}")
    if hasattr(content, 'claims'):
        print(f"Has claims: {content.claims}")
