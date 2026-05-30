"""Unified orchestrator: RegEx-first, AI fallback.

This is the single entry point for the full pipeline. It runs the deterministic
RegEx extractor first; only if that finds NO claim does it fall back to the AI
extractor. This keeps the common, well-structured prompts fast and free of model
calls, while still handling the harder / fuzzier cases with the LLM.

    from General_analysis import analyze_prompt_to_claims
    claims = analyze_prompt_to_claims("Bitcoin kısa vadede 103000 dolar olur.")

The individual layers remain usable on their own via `RegEx_analysis.py`
(`rule_based_claims_from_prompt`) and `AI_analysis.py` (`analyze_with_ai`).
"""

from typing import List

from RegEx_analysis import (
    FinancialClaim,
    extract_deadline,
    rule_based_claims_from_prompt,
)
from AI_analysis import analyze_with_ai


def analyze_prompt_to_claims(prompt: str) -> List[FinancialClaim]:
    """RegEx-first extraction; fall back to AI only when regex finds nothing.

    Step 1: run the deterministic RegEx extractor.
    Step 2: if it returns at least one claim, use it (no AI call needed).
    Step 3: otherwise, defer to the AI extractor.
    """
    regex_claims = rule_based_claims_from_prompt(prompt)
    if regex_claims:
        return regex_claims

    return analyze_with_ai(prompt)


def run_verifi(prompt: str):
    """Run the pipeline, then write one claim per line with Python formatting."""
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
                f"value={claim.value} | value_type={claim.value_type} | "
                f"deadline={deadline or 'null'} | status={claim.status}"
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
                    f"value={claim.value} | value_type={claim.value_type} | "
                    f"deadline={deadline or 'null'} | status={claim.status}"
                )
                f.write(line + "\n")
            f.write("\n")
            remaining = total - case_idx
            print(f"[{case_idx}/{total}] analyzed | remaining: {remaining}")


if __name__ == "__main__":
    def to_multisentence_inputs(claims: List[str], lang: str) -> List[str]:
        """Wrap claim text with realistic extra context (>=3 sentences)."""
        if lang == "tr":
            return [
                (
                    "Sabah ekip toplantısında önce ürün yol haritasını konuştuk. "
                    f"Sonra piyasaya dair görüşümü paylaştım: {claim} "
                    "Yine de risk yönetimi için pozisyonu kademeli açmayı planlıyorum."
                )
                for claim in claims
            ]
        return [
            (
                "In the morning sync we first reviewed product milestones. "
                f"Then I shared one market view: {claim} "
                "Even so, I would size positions gradually because volatility is still high."
            )
            for claim in claims
        ]

    price_claims_tr = [
        "Bitcoin kısa vadede 103000 dolar olur.",
        "Etheriyum orta vadede 6200 dollar olur.",
        "Solana yıl sonunda 320 USD olur.",
        "Binance coin kısa vadede 860 dolar olur.",
        "Apple hissesi orta vadede 290 dolar olur.",
        "Microsof yıl sonunda 640 dolar olur.",
        "Gogle kısa vadede 260 dollar olur.",
        "Amazn orta vadede 275 dolar olur.",
        "Nvida yıl sonunda 1400 USD olur.",
        "Tesl haftaya 360 dolar olur.",
        "Meta hissesi orta vadede 780 USD olur.",
        "Netfliix yıl sonunda 930 dollar olur.",
        "USD/TRY orta vadede 49.10 olur.",
        "EUR/USD kısa vadede 1.22 olur.",
        "GBP/USD yıl sonunda 1.45 olur.",
    ]
    price_claims_en = [
        "Bitcoin will reach 110000 dollars in the short term.",
        "Etherium will hit 6800 doller in the medium term.",
        "Solana will be 360 USD by year-end.",
        "Binance coin will be 920 dollars in the short term.",
        "Apple stock will be 305 dollars in the medium term.",
        "Microsof will be 670 dollars by year-end.",
        "Gogle will hit 270 dollars in the short term.",
        "Amazn will reach 285 dollars in the medium term.",
        "Nvida will be 1450 dollars by year-end.",
        "Tesl will be 375 dollars next week.",
        "Meta will be 820 USD in the medium term.",
        "Netflix will hit 960 USD by year-end.",
        "USD/JPY will test 170 in the short term.",
        "AUD/USD will be 0.79 in the medium term.",
        "CNY/TRY will be 7.60 by year-end.",
    ]
    price_claims = to_multisentence_inputs(price_claims_tr, "tr") + to_multisentence_inputs(price_claims_en, "en")

    percent_claims_tr = [
        "Bitcoin doler bazında yıl sonunda %12 artacak.",
        "Etheriyum dolar karşısında orta vadede yüzde 9 yükselecek.",
        "Solana BTC bazında kısa vadede %7 düşecek.",
        "Binance coin lira karşısında yıl sonunda yüzde 15 değer kazanacak.",
        "XRP USD bazında kısa vadede %6 artış gösterecek.",
        "ADA EUR karşısında orta vadede yüzde 4 azalış yaşayacak.",
        "AVAX dolar bazında haftaya %5 yükselecek.",
        "DOGE BTC karşısında kısa vadede yüzde 11 düşecek.",
        "DOT USD bazında yıl sonunda %8 artacak.",
        "LINK TRY karşısında orta vadede yüzde 10 değer kazanacak.",
        "Apple dolar bazında yıl sonunda %13 artacak.",
        "Microsof avro karşısında kısa vadede yüzde 3 düşecek.",
        "Gogle dolar bazında orta vadede %5 artış yaşayacak.",
        "Amazn lira karşısında yıl sonunda yüzde 14 yükselecek.",
        "Nvida dolar bazında kısa vadede %9 düşecek.",
    ]
    percent_claims_en = [
        "Bitcoin will rise by 12% against USD by year-end.",
        "Etheriyum will increase 8 percent versus dollar in the medium term.",
        "Solana will drop 6% against BTC in the short term.",
        "Binance coin will gain 14% against lira by year-end.",
        "XRP will increase 5% versus USD next week.",
        "ADA will fall 4 percent against EUR in the medium term.",
        "AVAX will rise 7% against USD in the short term.",
        "DOGE will drop 10% versus BTC by year-end.",
        "DOT will gain 9% against USD in the medium term.",
        "LINK will increase 11 percent against TRY in the short term.",
        "Apple will rise 6% against dollar by year-end.",
        "Microsof will decline 3% versus euro in the short term.",
        "Gogle will gain 4 percent against dollar in the medium term.",
        "Amazn will rise 8% against lira by year-end.",
        "Nvida will drop 5% versus dollar in the short term.",
    ]
    percent_claims = to_multisentence_inputs(percent_claims_tr, "tr") + to_multisentence_inputs(percent_claims_en, "en")

    possible_percentage_tr = [
        "Bitcoin %10 artacak.",
        "Etheriyum yüzde 8 düşecek.",
        "Apple %6 yükselecek.",
        "Gogle yüzde 5 azalır.",
        "Nvida %9 artış yaşayacak.",
        "Dolar %4 değer kazanacak.",
        "Avro yüzde 3 düşecek.",
        "Solana %12 yükselecek.",
    ]
    possible_percentage_en = [
        "Bitcoin will rise 10%.",
        "Etherium will drop 7 percent.",
        "Apple will gain 6%.",
        "Gogle will decline 5 percent.",
        "Nvida will increase 9%.",
        "Dollar will rise 4%.",
        "Euro will fall 3 percent.",
    ]
    possible_percentage_claims = to_multisentence_inputs(possible_percentage_tr, "tr") + to_multisentence_inputs(possible_percentage_en, "en")

    possible_price_tr = [
        "Solana 420 USD olacak.",
        "BNB 980 olacak.",
        "Microsof 720 bandını test eder.",
        "Amazn 310 dolar görür.",
        "Tesl 450 olur.",
        "Bitcoin 125000 olur.",
        "Etheriyum 7500 dolar olur.",
        "Apple 340 olur.",
    ]
    possible_price_en = [
        "Solana will be 420.",
        "BNB will hit 980 USD.",
        "Microsof will test 720.",
        "Amazn reaches 310 dollars.",
        "Tesl will be 450.",
        "Bitcoin will be 125000.",
        "Etherium will be 7500 dollars.",
    ]
    possible_price_claims = to_multisentence_inputs(possible_price_tr, "tr") + to_multisentence_inputs(possible_price_en, "en")

    noise_cases = [
        "Sabah erkenden yürüyüşe çıktım. Ofise dönünce e-postaları yanıtladım. Akşam da arkadaşlarımla buluştum.",
        "Bugün sadece tasarım revizyonlarını konuştuk. Ürün metinlerinde dil birliği eksikti. Yarın tekrar gözden geçireceğiz.",
        "Toplantı beklenenden kısa sürdü. Herkes görev listesini güncelledi. Sonra sprint planını kapattık.",
        "The weather was cloudy in the morning. I spent the afternoon fixing documentation typos. Tonight I will read a novel.",
        "We discussed onboarding friction in user interviews. The team proposed three UX changes. Final decisions will be made tomorrow.",
        "Yeni kahve makinesi sonunda geldi. Mutfakta küçük bir düzenleme yaptık. Herkes öğleden sonra daha enerjikti.",
        "I reviewed pull requests for two hours. Then I prepared release notes for the mobile app. Nothing else happened today.",
        "Hafta sonu için gezi planı yaptık. Otel rezervasyonunu tamamladık. Yolculuk listesini de hazırladık.",
        "The design team requested new icon variants. Marketing asked for copy tweaks on the homepage. Support also shared user feedback.",
        "Ofiste internet bir süre yavaştı. Teknik ekip modemleri yeniden başlattı. Akşam üstü bağlantı normale döndü.",
    ]

    test_cases = price_claims + percent_claims + possible_percentage_claims + possible_price_claims + noise_cases

    if len(test_cases) != 100:
        raise ValueError(f"Expected 100 test cases, got {len(test_cases)}")
    try:
        run_test_cases(test_cases, output_file="test_results.txt")
        print("100 test case sonucu test_results.txt dosyasına yazıldı.")
    except Exception as e:
        print(f"Hata: {e}")
