import re
import json
import time
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from schema import HardClaimExtractor

# LM Studio model listesindeki tam kimlik (ID)
ACTIVE_MODEL_ID = "ministral-3-8b-instruct-2512"

local_llm = OpenAIChat(
    id=ACTIVE_MODEL_ID,
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

SYSTEM_INSTRUCTIONS = [
    """### ROLE
Sen, yüksek hassasiyetli bir "Financial Hard Claim Extractor" (Finansal Kesin İddia Çıkarıcı) yapay zekasın. Görevin, metindeki gürültüyü temizlemek ve sadece doğrulanabilir, ölçülebilir finansal tahminleri ayıklamaktır.

### SCOPE & FILTERING
1. KAPSAM: Sadece ekonomi, borsa, döviz, emtia, kripto para ve makroekonomik (enflasyon, faiz vb.) tahminleri işle.
2. RED KRİTERİ: Hava durumu, spor, siyaset (ekonomik etkisi yoksa) veya kişisel niyetler ("almayı planlıyorum" gibi) KAPSAM DIŞIDIR. Bu durumda `status: "out_of_scope"` döndür.
3. ÖLÇÜLEBİLİRLİK: "Fırlayacak", "çökecek", "çok artacak" gibi ifadeler iddia DEĞİLDİR. İddia sayılması için metinde mutlaka rakam, yüzde, fiyat hedefi veya net bir oran bulunmalıdır.

### EXTRACTION RULES (STRICT)
Bir cümleyi 'claims' listesine eklemek için şu 3 bileşenin de metinde olması ŞARTTIR:
- Özne/Nesne (Subject): İddia ne hakkında? (Örn: "Bitcoin", "Gram Altın")
- Miktar (Quantity): Hedeflenen rakam veya değişim oranı? (Örn: "120.000$", "%15 artış")
- Zaman (Time Frame): Bu tahmin ne zaman için? (Örn: "2026 sonu", "önümüzdeki ay")
*Eksik bileşen varsa o iddiayı asla listeye ekleme.*

### OUTPUT FORMATTING (CRITICAL)
- SADECE ham JSON döndür. 
- Markdown blokları (```json ... ```), giriş cümlesi veya "İşte sonuçlar" gibi açıklamalar ASLA yapma.
- JSON içinde Python 'None' kullanma, standart JSON 'null' kullan.
- Tüm değerleri çift tırnak içinde STRING olarak döndür.
- KESİN ANAHTARLAR: "subject_object", "quantity", "time_frame", "claim_text".

### SCHEMA RECAP
{
  "detected_language": "tr/en",
  "status": "success/out_of_scope",
  "claims": [
    {
      "subject_object": "string",
      "quantity": "string",
      "time_frame": "string",
      "claim_text": "Cümlenin orijinal hali"
    }
  ],
  "reason": "Reddedilme nedeni (opsiyonel)"
}

### SELF-VERIFICATION STEP
Çıktı üretmeden önce kontrol et:
- "Miktar kısmında bir rakam veya yüzde var mı?" -> Yoksa sil.
- "Zaman belirtilmiş mi?" -> Belirtilmemişse sil.
- "JSON anahtarları doğru mu?" -> 'entity' veya 'amount' yazdıysan 'subject_object' ve 'quantity' olarak düzelt.
"### ÖRNEK (FEW-SHOT):",
    "Girdi: 'Dolar 40 TL, Euro 45 TL olacak.'",
    "Çıktı: {",
    "  'status': 'success',",
    "  'claims': [",
    "    {'subject_object': 'Dolar', 'quantity': '40 TL', 'time_frame': 'belirtilmemiş', 'claim_text': 'Dolar 40 TL olacak'},",
    "    {'subject_object': 'Euro', 'quantity': '45 TL', 'time_frame': 'belirtilmemiş', 'claim_text': 'Euro 45 TL olacak'}",
    "  ]",
    "}",

    "### ÖRNEK 2 (SHARED TIME):",
    "Girdi: 'BTC ve ETH 2026 sonunda rekor kıracak; BTC 100k, ETH 8k olur.'",
    "Çıktı: {",
    "  'status': 'success',",
    "  'claims': [",
    "    {'subject_object': 'BTC', 'quantity': '100k', 'time_frame': '2026 sonu', 'claim_text': 'BTC 100k olur'},",
    "    {'subject_object': 'ETH', 'quantity': '8k', 'time_frame': '2026 sonu', 'claim_text': 'ETH 8k olur'}",
    "  ]",
    "}"

"""
]

agent = Agent(model=local_llm, instructions=SYSTEM_INSTRUCTIONS)

def clean_and_repair_json(raw_text):
    start = raw_text.find('{')
    end = raw_text.rfind('}') + 1
    if start == -1 or end == 0: return None
    json_str = raw_text[start:end]
    return json_str.replace(": None", ": null").replace(":None", ":null")

TEST_CASES = [
    # 1. Factual & Measurable
    "I believe Bitcoin will hit $120,000 by the end of 2026.",
    "Bence gram altın yıl sonunda 4500 TL seviyesini görecek.",
    "I predict Tesla stock prices will drop by 15% after the next earnings call.",
    "Dolar kurunun önümüzdeki ay 38 TL'ye çıkacağını tahmin ediyorum.",
    
    # 2. Multi-Claim
    "I expect Bitcoin to hit $100k and Ethereum to reach $8k by the end of 2026.",
    "Tahminimce yıl sonunda dolar 40 TL, euro ise 45 TL olacak.",
    "I bet Brent oil will drop to $70 next month while gold surges to $2500.",
    "Bence 2027 başında enflasyon %15'e gerilerken büyüme %4'e çıkacak.",
    
    # 3. Combined Quantitative
    "Konut fiyatlarının 6 ayda %20, 1 yılda ise toplam %50 artacağını sanıyorum.",
    "I think interest rates will stay at 5% in July and rise to 5.5% in September.",
    
    # 4. Noise / Near-Miss (Bunların elenmesi beklenir)
    "Bence borsa ve döviz bu yıl çok fena patlayacak.",
    "I believe tech stocks will outperform energy stocks next year.",
    "Gelecek ay hem altın hem gümüş almayı planlıyorum."
]


def start_single_test():
    print(f"--- 🚀 Tek Model Testi Başlatıldı: [{ACTIVE_MODEL_ID}] ---")
    
    for i, test_input in enumerate(TEST_CASES, 1):
        print(f"\nTEST #{i}: {test_input}")
        try:
            response = agent.run(test_input)
            clean_json = clean_and_repair_json(response.content)
            data = HardClaimExtractor.model_validate_json(clean_json)
            
            # Kod tarafında geçerlilik kontrolü
            valid_claims = [c for c in data.claims if c.is_valid_claim()]
            
            if not valid_claims:
                print("  ⚠️ Durum: Geçerli finansal iddia bulunamadı.")
            else:
                for c in valid_claims:
                    print(f"  ✅ Bulundu: {c.subject_object} | {c.quantity} | {c.time_frame}")

        except Exception as e:
            print(f"  ❌ Hata: {e}")

if __name__ == "__main__":
    start_single_test()