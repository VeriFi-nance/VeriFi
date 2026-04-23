import os
import json
import re
from datetime import datetime
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from schema import HardClaimExtractor, SingleClaim, VALID_ASSETS

# --- 1. MODEL YAPILANDIRMASI (LM Studio) ---
local_llm = OpenAIChat(
    id="ministral-3-8b-instruct-2512",
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

# --- 2. SYSTEM PROMPT ---
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

# --- 3. AGENT KURULUMU ---
verifi_agent = Agent(
    model=local_llm,
    instructions=get_verifi_instructions(),
    # response_model should be passed per-call to Agent.run(), not to the constructor
    markdown=False
)

# --- 4. HELPER FUNCTIONS ---
def extract_json_from_text(text):
    """Extract valid JSON object from text that may contain extra content."""
    if not text:
        return None
    
    # Remove markdown code fences if present
    text = text.replace('```json', '').replace('```', '')
    
    # Try to find JSON block
    start = text.find('{')
    end = text.rfind('}') + 1
    
    if start == -1 or end == 0:
        return None
    
    json_str = text[start:end]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Try to repair common JSON issues
        try:
            # Replace single quotes with double quotes
            json_str_fixed = json_str.replace("'", '"')
            return json.loads(json_str_fixed)
        except:
            return None

def normalize_response(response):
    """Convert agent response to list of claims (dicts or objects)."""
    claims_list = []
    
    if response is None:
        return claims_list
    
    # If it's a string, try to parse JSON
    if isinstance(response, str):
        parsed = extract_json_from_text(response)
        if parsed and isinstance(parsed, dict):
            claims_list = parsed.get('claims', [])
        return claims_list
    
    # If it's a Pydantic model, get claims attribute
    if hasattr(response, 'claims'):
        claims_data = getattr(response, 'claims')
        if isinstance(claims_data, list):
            claims_list = claims_data
    
    return claims_list

def get_claim_field(obj, *keys):
    """Safely extract field from claim object or dict, trying multiple key names."""
    for key in keys:
        if isinstance(obj, dict):
            val = obj.get(key, '')
        else:
            val = getattr(obj, key, '')
        
        if val and val != '':
            return str(val).replace('\n', ' ').replace('\r', ' ').strip()
    
    return ''

def is_valid_claim(c):
    """Check if claim has minimum required fields."""
    base = get_claim_field(c, 'base_asset', 'subject_object')
    amount = get_claim_field(c, 'amount', 'quantity')
    return bool(base and amount)

# --- 5. ANA DÖNGÜ (DOSYA İŞLEME) ---
def run_verifi_extraction(input_file="claims.txt", output_file="verifi_results.txt", debug=False):
    if not os.path.exists(input_file):
        print(f"❌ Hata: {input_file} dosyası bulunamadı.")
        return

    print(f"--- 🚀 VeriFi Extractor Başladı ---")
    
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    success_count = 0
    filtered_count = 0
    error_count = 0

    with open(output_file, "w", encoding="utf-8") as out:
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            try:
                # Agno Agent çalıştırılır; response_model veriyi parse etmek için kullanılır
                response = verifi_agent.run(line, response_model=HardClaimExtractor)
                
                # Extract content from response
                extraction = getattr(response, 'content', response) if response else None
                
                if debug and i <= 3:
                    print(f"DEBUG {i}: extraction type = {type(extraction)}, value = {str(extraction)[:100]}")
                
                # Normalize to list of claims (dicts or objects)
                claims_list = normalize_response(extraction)

                if claims_list and len(claims_list) > 0:
                    for c in claims_list:
                        # Extract fields safely
                        if not is_valid_claim(c):
                            continue
                            
                        base = get_claim_field(c, 'base_asset', 'subject_object')
                        quote = get_claim_field(c, 'quote_asset', 'target_asset')
                        amount = get_claim_field(c, 'amount', 'quantity')
                        unit = get_claim_field(c, 'unit', 'unit_type')
                        time_frame = get_claim_field(c, 'time_frame', 'target_date', 'vade')
                        status = get_claim_field(c, 'status', 'status_type')

                        result_row = (
                            f"Satır {i} | {base}/{quote} | "
                            f"Hedef: {amount} ({unit}) | "
                            f"Vade: {time_frame or 'Belirsiz'} | Status: {status}"
                        )
                        out.write(result_row + "\n")
                        print(f"✅ Çıkarıldı: {base} - {amount}")
                        success_count += 1
                else:
                    print(f"⚠️ Atlandı (Filtre): {line[:40]}...")
                    filtered_count += 1

            except Exception as e:
                if debug:
                    print(f"❌ Satır {i} Hatası: {str(e)}")
                else:
                    print(f"❌ Satır {i} Hatası: {str(e)[:60]}")
                error_count += 1

    print(f"\n✅ İşlem tamam!")
    print(f"   Başarı: {success_count} | Filtre: {filtered_count} | Hata: {error_count}")
    print(f"   Sonuçlar '{output_file}' dosyasına kaydedildi.")

if __name__ == "__main__":
    # Run with debug=True to see first 3 lines of raw LLM output
    lines = open("claims.txt").readlines()[:5]
with open("test_claims_5.txt", "w") as f:
    f.writelines(lines)
run_verifi_extraction("test_claims_5.txt", "test_output.txt", debug=False)