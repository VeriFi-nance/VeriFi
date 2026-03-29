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
def clean_and_repair_json(raw_text):
    """LLM'den gelen metindeki JSON'u bulur ve temizler."""
    if not raw_text: return None
    try:
        start = raw_text.find('{')
        end = raw_text.rfind('}') + 1
        if start == -1 or end == 0: return None
        json_str = raw_text[start:end]
        # Python'un None değerini JSON null'a çevirir
        return json_str.replace(": None", ": null").replace(":None", ":null")
    except Exception:
        return None
from datetime import datetime, timedelta

from datetime import datetime, timedelta

def get_financial_claim_extractor_system_prompt():
    """
    Dengeli Few-Shot (Single, Multi, Filtered) içeren ve katı JSON formatına 
    zorlanmış V4 System Prompt'u. Küçük modellerdeki overfitting'i önler.
    """
    now = datetime.now()
    
    current_year = now.year
    current_date = now.strftime("%d %B %Y")
    
    short_term = (now + timedelta(days=90)).strftime('%Y-%m-%d')
    medium_term = (now + timedelta(days=365)).strftime('%Y-%m-%d')
    long_term = (now + timedelta(days=1095)).strftime('%Y-%m-%d')

    PROMPT = f"""
### ROLE
Sen, finansal metinlerden kullanıcının bizzat sahiplendiği veya onayladığı "Doğrulanabilir İddiaları" (Verifiable Claims) ayıklayan uzman bir analizcisin.
Görev: Gürültüyü elemek ve sadece test edilebilir, somut iddiaları ayıklamaktır.

### 1. VERIFIABILITY & OWNERSHIP KONTROLÜ
Şu üç kriterden BİRİ BİLE EKSİKSE cümleyi ayıklama (status: "filtered" yap):
- SAHİPLİK: Kullanıcının kendi tahmini mi? ("Beklentim", "Bence" -> EVET | "Haberlere göre", "X dedi ki" -> HAYIR) (Cümle doğrudan bir yargı bildiriyorsa ("X olacak", "Y artar") veya onay veriyorsa ("katılıyorum", "onaylıyorum") EVET kabul et. SADECE başkasının ağzından alıntı yapılıyorsa ve kullanıcı yorum katmıyorsa ("X bankası dedi ki", "Habere göre", "Analistler diyor") HAYIR kabul et.)
- ÜÇLÜ BİLEŞEN: Şu üçü kesinlikle var mı? 1. Özne (Varlık) 2. Miktar (%, rakam, dip) 3. Zaman (Vade, tarih).
- KAPSAM DIŞI: Sadece duygu belirten veya belirsiz yorumları ele.

### 2. ÖRNEKLER (DENGELİ FEW-SHOT)
Aşağıdaki 3 farklı senaryoyu dikkatle incele ve çıktı üretirken bu mantığı birebir kopyala. Her cümleyi zorla ikiye bölmeye çalışma, sadece gerekliyse böl!

SENARYO A (Single Claim - Tek İddia):
Girdi: "Bence dolar yıl sonunda 40 TL olacak."
Çıktı:
{{
  "detected_language": "tr",
  "status": "success",
  "claims": [
    {{
      "subject_object": "Dolar",
      "quantity": "40 TL olacak",
      "time_frame": "Yıl sonunda",
      "target_date": "{current_year}-12-31",
      "claim_text": "Dolar yıl sonunda 40 TL olacak."
    }}
  ]
}}

SENARYO B (Multi-Claim - Birden Fazla İddia İçeren Cümle):
Girdi: "Altın ay sonunda %5 artacak ama gümüş yıl sonuna kadar %10 düşebilir."
Çıktı:
{{
  "detected_language": "tr",
  "status": "success",
  "claims": [
    {{
      "subject_object": "Altın",
      "quantity": "%5 artacak",
      "time_frame": "Ay sonu",
      "target_date": "{current_year}-10-31",
      "claim_text": "Altın ay sonunda %5 artacak."
    }},
    {{
      "subject_object": "Gümüş",
      "quantity": "%10 düşebilir",
      "time_frame": "Yıl sonuna kadar",
      "target_date": "{current_year}-12-31",
      "claim_text": "Gümüş yıl sonuna kadar %10 düşebilir."
    }}
  ]
}}

SENARYO C (Filtered - Gürültü/Kriter Dışı):
Girdi: "Piyasalar çok heyecanlı, haberlere göre Merkez Bankası faiz artırabilirmiş."
(Sebep: Sahiplik yok 'haberlere göre' diyor, kesin miktar yok, kesin zaman yok.)
Çıktı:
{{
  "detected_language": "tr",
  "status": "filtered",
  "reason": "MISSING_TRIPLE_COMPONENT",
  "claims": []
}}

### 3. DATE & TIME REFERENCE
- Bugün: {current_date} | Referans Yıl: {current_year}
- Dönemler: Q1->{current_year}-03-31 | Q2->{current_year}-06-30 | Q3->{current_year}-09-30 | Q4->{current_year}-12-31 | H1->{current_year}-06-30 | H2->{current_year}-12-31.
- Varsayılan Vadeler: Kısa->{short_term} | Orta->{medium_term} | Uzun->{long_term}.

### 4. STRICT OUTPUT FORMAT (KRİTİK)
SADECE VE SADECE JSON formatında yanıt ver. 
Yanıtın KESİNLİKLE {{ karakteri ile başlamalı ve }} karakteri ile bitmelidir.
Başında veya sonunda "İşte sonuç", "```json" gibi HİÇBİR açıklama veya Markdown işareti KULLANMA. Asla formatı bozma.
ASLA JSON İÇİNE YORUM SATIRI (// veya #) EKLEME.
"""
    return PROMPT
# Kullanım:
SYSTEM_INSTRUCTIONS = get_financial_claim_extractor_system_prompt()

agent = Agent(model=local_llm, instructions=SYSTEM_INSTRUCTIONS)

import random
import json
import re
from datetime import datetime

def clean_json_comments(text):
    """JSON içindeki // veya # ile başlayan yorumları temizler."""
    # Satır sonundaki // ... veya # ... yorumlarını temizle
    text = re.sub(r'(//|#).*$', '', text, flags=re.MULTILINE)
    return text
def get_expected_stats(line_no):
    """Volkan'ın yeni aralıklarına göre güncellendi."""
    if 1 <= line_no <= 800:
        return "Single Claim", 1
    elif 801 <= line_no <= 1072:
        return "Multi Claim", 2
    elif 1073 <= line_no <= 1350: # 1072 sonrası Noise kabul edildi
        return "Noise", 0
    return "Unknown", -1
def run_balanced_test_with_debug(file_path="claims.txt"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Hata: {file_path} bulunamadı!")
        return

    # Havuzlar
    single_pool = list(range(1, 801))
    multi_pool = list(range(801, 1073))
    noise_pool = list(range(1073, 1324))

    sampled_indices = (
        random.sample(single_pool, 40) +
        random.sample(multi_pool, 40) +
        random.sample(noise_pool, 20)
    )
    random.shuffle(sampled_indices)

    stats = {
        "Single Claim": {"tested": 0, "correct": 0},
        "Multi Claim": {"tested": 0, "correct": 0},
        "Noise": {"tested": 0, "correct": 0}
    }
    
    total_correct = 0
    
    print(f"--- 🛠️ [DEBUG] {ACTIVE_MODEL_ID} | 40/40/20 Test Başlatıldı ---\n")

    for i, line_no in enumerate(sampled_indices, 1):
        line_content = all_lines[line_no - 1].strip()
        category, expected_count = get_expected_stats(line_no)
        stats[category]["tested"] += 1
        
        found_count = 0
        raw_content = ""
        
        try:
            response = agent.run(line_content)
            raw_content = response.content
            
            # JSON Tamiri: Yorumları temizle ve Markdown bloklarını ayıkla
            clean_text = clean_and_repair_json(raw_content) # Senin mevcut fonksiyonun
            clean_text = clean_json_comments(clean_text)    # Yeni eklediğimiz yorum temizleyici
            
            try:
                data = json.loads(clean_text)
                # Sadece claims listesinin uzunluğuna bakıyoruz
                if data.get("status") == "success" and "claims" in data:
                    found_count = len(data["claims"])
                else:
                    found_count = 0
            except:
                found_count = -1 # Hala parse edilemiyorsa

            is_correct = (found_count == expected_count)
            if is_correct:
                stats[category]["correct"] += 1
                total_correct += 1
                status_icon = "✅"
            else:
                status_icon = f"❌ (B:{expected_count} F:{found_count})"

            print(f"[{i:03}/100] Satır {line_no:4} | {status_icon} | {category}")

            # Sadece hata aldığında bas (İstersen kapatabilirsin)
            if not is_correct:
                print(f"> Girdi: {line_content}")
                print(f"> Model Yanıtı: {raw_content.strip()}")
                print("-" * 50)

        except Exception as e:
            print(f"[{i:03}/100] Satır {line_no:4} | ⚠️ Sistem Hatası: {str(e)[:50]}")

        # Tablo Raporu (Öncekiyle aynı format)
    print("\n" + "="*60)
    print(f"📈 FİNAL SONUÇLARI - {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 60)
    for cat in ["Single Claim", "Multi Claim", "Noise"]:
        v = stats[cat]
        acc = (v["correct"]/v["tested"]*100) if v["tested"] > 0 else 0
        print(f"{cat:<15} | {v['tested']:<6} | {v['correct']:<8} | %{acc:.1f}")
    print("-" * 60)
    print(f"GENEL TOPLAM    | 100    | {total_correct:<8} | %{total_correct:.1f}")
    print("="*60)
if __name__ == "__main__":
    run_balanced_test_with_debug()