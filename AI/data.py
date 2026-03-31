import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

class TradingViewScraper:
    def __init__(self):
        chrome_options = Options()
        # chrome_options.add_argument("--headless") # Tarayıcıyı görmeden arka planda çalıştırmak istersen açabilirsin
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.raw_file = "claims_raw.txt"
        
    def clean_claim(self, text):
        # "Analist X diyor ki" gibi kalıpları temizlemek veya sadece iddiaya odaklanmak için basit temizlik
        # TradingView metinleri genelde doğrudan iddia içerir.
        text = text.replace("\n", " ").strip()
        # Çok kısa veya anlamsız metinleri ele
        if len(text) < 20: return None
        return text

    def is_valid_claim(self, text):
        # Sayı içermeli (Quantity kısıtı)
        if not re.search(r'\d', text): return False
        
        # Gelecek zaman veya hedef belirten anahtar kelimeler
        keywords = [
            "hedef", "seviye", "bekliyorum", "target", "will", "level", 
            "reach", "vade", "term", "forecast", "prediction", "görecek"
        ]
        return any(kw in text.lower() for kw in keywords)

    def scrape_ideas(self, url, limit=500):
        self.driver.get(url)
        time.sleep(5) # Sayfanın yüklenmesini bekle
        
        claims_found = 0
        seen_texts = set()

        while claims_found < limit:
            # Idea kartlarını bul (TradingView class'ları zamanla değişebilir, selector'ı kontrol et)
            # Şu anki yapıda açıklama metinleri genellikle 'description-' içeren class'larda bulunur.
            cards = self.driver.find_all(By.CSS_SELECTOR, "div[class*='description-']")
            
            for card in cards:
                raw_text = card.text
                if raw_text not in seen_texts:
                    seen_texts.add(raw_text)
                    if self.is_valid_claim(raw_text):
                        cleaned = self.clean_claim(raw_text)
                        if cleaned:
                            with open(self.raw_file, "a", encoding="utf-8") as f:
                                f.write(cleaned + "\n")
                            claims_found += 1
                            if claims_found % 10 == 0:
                                print(f"Şu ana kadar {claims_found} gerçek iddia toplandı...")
                
                if claims_found >= limit: break

            # Sayfayı aşağı kaydır (Yeni içerik yüklemesi için)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3) # Yükleme süresi

    def run(self):
        # Türkçe Kaynaklar
        print("Türkçe iddialar toplanıyor...")
        self.scrape_ideas("https://tr.tradingview.com/ideas/", limit=250)
        
        # İngilizce Kaynaklar
        print("İngilizce iddialar toplanıyor...")
        self.scrape_ideas("https://www.tradingview.com/ideas/", limit=500) # Toplamda 500-1000 arası
        
        self.driver.quit()
        print(f"İşlem tamamlandı. Veriler {self.raw_file} dosyasına kaydedildi.")

if __name__ == "__main__":
    scraper = TradingViewScraper()
    scraper.run()