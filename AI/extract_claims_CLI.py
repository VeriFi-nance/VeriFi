from new_main import analyze_prompt_to_claims, rule_based_claims_from_prompt

def extract_claims_CLI(use_rule_based=False) -> None:
    """Run interactive terminal mode until user types exit.
    When use_rule_based is True, it uses the rule-based extraction method instead of the LLM-based one.
    Otherwise, first LLM-based extraction is attempted, and if it fails, it falls back to the rule-based method."""
    print("VeriFi interactive extraction CLI started. Type 'exit' to quit.")
    while True:
        user_input = input("Enter claim text: ").strip()
        if user_input.lower() == "exit":
            print("Exiting VeriFi interactive extraction CLI.")
            break
        if not user_input:
            print("Please enter a non-empty text.")
            continue
        try:
            if use_rule_based:
                claims = rule_based_claims_from_prompt(user_input)
            else:
                claims = analyze_prompt_to_claims(user_input)
            if not claims:
                print("No valid claims extracted.")
                continue
            for idx, claim in enumerate(claims, start=1):
                print(
                    f"{idx}. pay={claim.pay} | payda={claim.payda or 'null'} | "
                    f"value={claim.value} | value_type={claim.value_type} | "
                    f"deadline={claim.deadline or 'null'} | status={claim.status}"
                )
        except Exception as e:
            print(f"Hata: {e}")


if __name__ == "__main__":
    extract_claims_CLI()