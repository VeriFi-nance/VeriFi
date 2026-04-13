import os
from agno.agent import Agent
from agno.models.openai import OpenAIChat
import re
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from datetime import datetime, timedelta

# VeriFi V3: Gelişmiş Mermi Ayıklayıcı (Pro-Extractor)
# Bu Agent, "Dolar 50 Lira" halüsinasyonunu kırmak ve gürültüyü (noise) 
# %100 isabetle ayırt etmek için tasarlanmıştır.

claim_agent = Agent(
    model=OpenAIChat(
        id="mistralai/ministral-3-14b-reasoning", # LM Studio'daki model isminizle eşleşmeli
        base_url="http://localhost:1234/v1",       # LM Studio Yerel Sunucu
        api_key="lm-studio",                       # LM Studio için dummy key
    ),
    description="Sen finansal metinlerden 'Hard-Claim' ayıklayan uzman bir veri mühendisisin.",
    instructions=[
        "GÖREV: Sana verilen her cümleyi 'Sert Filtre' (Hard-Filter) süzgecinden geçir.",
        
        "1. SERT FİLTRE: Bir cümle claim sayılabilmesi için [Entity, Period, Quantity] öğelerinin üçünü de barındırmalıdır.",
        "- Entity: Net finansal özne (S&P 500, Brent, GSYH, Faiz vb.)",
        "- Period: Geleceğe dair net zaman damgası (2026 sonu, Q3, ay sonu vb.)",
        "- Quantity: Net sayısal değer veya oran (%12, 7600, 50 TL vb.)",
        "- KRİTİK: Eğer bu üçünden biri bile eksikse, o cümle GÜRÜLTÜDÜR (NOISE).",

        "2. ANTİ-HALÜSİNASYON:",
        "- Talimatlardaki örnek değerleri (dolar, 50 TL gibi) ASLA girdi metninde yoksa kullanma.",
        "- Girdideki özne neyse çıktıdaki de o olmalı. S&P 500'ü 'dolar' olarak etiketleme.",
        "- Eğer miktar veya vadeyi net bulamıyorsan, uydurma; o cümleyi gürültü kabul et.",

        "3. ZAMAN KONTROLÜ:",
        "- Sadece geleceğe yönelik projeksiyonları (bekleniyor, hedefleniyor, öngörülüyor) al.",
        "- Geçmiş verileri (gerçekleşti, açıklandı, ulaştı) kesinlikle GÜRÜLTÜ kabul et.",

        "4. ÇIKTI FORMATI:",
        "- Sadece şu formatı kullan: Varlık, Vade, Miktar|",
        "- Bir cümlede birden fazla iddia varsa '|' ile ayır.",
        "- Cümle GÜRÜLTÜ (Noise) ise sadece '|' karakterini döndür.",
        "- Kesinlikle 'thought', 'output:', 'input:' gibi ek açıklamalar yazma.",
    ],
)

def process_sentences(input_file):
    output_file = "claims_output_v3.txt"
    
    if not os.path.exists(input_file):
        print(f"Hata: {input_file} dosyası bulunamadı.")
        return

    print(f"--- VeriFi V3: 261 Cümlelik İşlem Başladı ---")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        sentences = f.readlines()

    with open(output_file, 'w', encoding='utf-8') as out_f:
        for idx, line in enumerate(sentences, 1):
            sentence = line.strip()
            if not sentence:
                continue
            
            try:
                # Agent'ı çalıştır
                response = claim_agent.run(sentence)
                
                if response and response.content:
                    # Sadece temiz sonucu al (Thought veya prefixleri temizle)
                    result = response.content.strip()
                    
                    # Loglama ve dosyaya yazma
                    print(f"[{idx}/261] In: {sentence}...")
                    print(f"       Out: {result}")
                    
                    out_f.write(f"{result}\n")
                    out_f.flush() # Her satırda dosyayı güncelle
                
            except Exception as e:
                print(f"Hata (Satır {idx}): {e}")

    print(f"\n--- İşlem Tamamlandı! Sonuçlar '{output_file}' dosyasına mermi gibi dizildi. ---")

if __name__ == "__main__":
    process_sentences("sentences.txt")