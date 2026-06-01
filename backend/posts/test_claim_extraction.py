from datetime import datetime, timezone
from django.test import TestCase
from posts.claim_extraction import rule_based_claims_from_prompt, has_asset_signal, passes_prefilter


class ClaimExtractionTests(TestCase):
    def setUp(self):
        # We lock the base date for relative deadline calculation.
        self.base_date = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_has_asset_signal(self):
        self.assertTrue(has_asset_signal("Bitcoin will rise"))
        self.assertTrue(has_asset_signal("$1000"))
        self.assertTrue(has_asset_signal("BTC/USD parity"))
        self.assertFalse(has_asset_signal("Hello world, no assets here"))

    def test_passes_prefilter(self):
        # True if asset signal and either a digit or relative deadline is present
        self.assertTrue(passes_prefilter("BTC is going to 100k"))
        self.assertTrue(passes_prefilter("Dolar haftaya"))  # Relative deadline, no digit
        self.assertFalse(passes_prefilter("BTC has been stable"))  # Asset, but no number or deadline
        self.assertFalse(passes_prefilter("going up 10% tomorrow"))  # Number & deadline, but no asset

    def test_extract_basic_percentage_up(self):
        prompt = "Bitcoin will go up 10% in 2 weeks"
        claims = rule_based_claims_from_prompt(prompt, base_date=self.base_date)
        self.assertEqual(len(claims), 1)
        c = claims[0]
        self.assertEqual(c.pay, "BTC")
        self.assertEqual(c.value, 10.0)
        self.assertEqual(c.value_type, "PERCENTAGE_UP")
        self.assertEqual(c.deadline, "2026-06-15")
        self.assertEqual(c.status, "INCOMPLETE_CLAIM")  # Incomplete because payda is None

    def test_extract_basic_percentage_down(self):
        prompt = "ETH will fall 15% next month"
        claims = rule_based_claims_from_prompt(prompt, base_date=self.base_date)
        self.assertEqual(len(claims), 1)
        c = claims[0]
        self.assertEqual(c.pay, "ETH")
        self.assertEqual(c.value, 15.0)
        self.assertEqual(c.value_type, "PERCENTAGE_DOWN")
        self.assertEqual(c.deadline, "2026-07-01")

    def test_extract_absolute_price(self):
        prompt = "BTC hits 103000 USD by end of year"
        claims = rule_based_claims_from_prompt(prompt, base_date=self.base_date)
        self.assertEqual(len(claims), 1)
        c = claims[0]
        self.assertEqual(c.pay, "BTC")
        self.assertEqual(c.value, 103000.0)
        self.assertEqual(c.value_type, "PRICE")
        self.assertEqual(c.payda, "USD")
        self.assertEqual(c.deadline, "2026-12-31")
        self.assertEqual(c.status, "HARD_CLAIM")  # All fields present

    def test_extract_turkish_relative_deadline(self):
        prompt = "Dolar 30 lira olur haftaya"
        claims = rule_based_claims_from_prompt(prompt, base_date=self.base_date)
        self.assertEqual(len(claims), 1)
        c = claims[0]
        self.assertEqual(c.pay, "USD")
        self.assertEqual(c.payda, "TRY")
        self.assertEqual(c.value, 30.0)
        self.assertEqual(c.value_type, "PRICE")
        self.assertEqual(c.deadline, "2026-06-08")  # +7 days
        self.assertEqual(c.status, "HARD_CLAIM")

    def test_multiple_claims_extraction(self):
        prompt = "BTC will rise 10% USD and ETH will fall 5% USD by tomorrow"
        claims = rule_based_claims_from_prompt(prompt, base_date=self.base_date)
        self.assertEqual(len(claims), 2)
        
        # Claims are sorted by position in text
        btc_claim = claims[0]
        self.assertEqual(btc_claim.pay, "BTC")
        self.assertEqual(btc_claim.payda, "USD")
        self.assertEqual(btc_claim.value, 10.0)
        self.assertEqual(btc_claim.value_type, "PERCENTAGE_UP")
        self.assertEqual(btc_claim.deadline, "2026-06-02")

        eth_claim = claims[1]
        self.assertEqual(eth_claim.pay, "ETH")
        self.assertEqual(eth_claim.payda, "USD")
        self.assertEqual(eth_claim.value, 5.0)
        self.assertEqual(eth_claim.value_type, "PERCENTAGE_DOWN")
        self.assertEqual(eth_claim.deadline, "2026-06-02")

    def test_incomplete_claim_anchor_rule(self):
        # Asset next to deadline, no value
        prompt = "Dolar haftaya ne olur?"
        claims = rule_based_claims_from_prompt(prompt, base_date=self.base_date)
        self.assertEqual(len(claims), 1)
        c = claims[0]
        self.assertEqual(c.pay, "USD")
        self.assertEqual(c.value, None)
        self.assertEqual(c.deadline, "2026-06-08")
        self.assertEqual(c.status, "INCOMPLETE_CLAIM")

    def test_quarter_and_half_deadlines(self):
        q_prompt = "Solana will pump to 200 USD in Q3 2026"
        claims = rule_based_claims_from_prompt(q_prompt, base_date=self.base_date)
        self.assertEqual(claims[0].deadline, "2026-09-30")

        h_prompt = "Apple will drop 5% by first half of 2027"
        claims = rule_based_claims_from_prompt(h_prompt, base_date=self.base_date)
        self.assertEqual(claims[0].deadline, "2027-06-30")

    def test_empty_or_no_signal_returns_empty(self):
        self.assertEqual(rule_based_claims_from_prompt("", base_date=self.base_date), [])
        self.assertEqual(rule_based_claims_from_prompt("I think the weather is nice today", base_date=self.base_date), [])
