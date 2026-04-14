from datetime import date, timedelta
from unittest.mock import patch
from django.test import TestCase
from posts.models import Asset, Post, HardClaim, HardClaimEvent
from posts.resolution import (
    normalize_claim_for_resolution,
    evaluate_claim,
    resolve_hard_claim,
    ResolutionError,
)

from accounts.models import WalletUser
from django.utils import timezone

class ResolutionTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.COINGECKO,
            provider_symbol="bitcoin",
            quote_currency="USD",
        )
        self.author = WalletUser.objects.create(address="0x123")
        self.post = Post.objects.create(
            author=self.author,
            content="Content",
        )
        self.claim = HardClaim.objects.create(
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage="10.00",
            until=date.today() + timedelta(days=1), # initially future to pass create
            status=HardClaim.Status.UNDETERMINED,
        )
        # Backdate so it counts as due
        HardClaim.objects.filter(id=self.claim.id).update(
            created_at=timezone.now() - timedelta(days=5),
            until=date.today() - timedelta(days=1)
        )
        self.claim.refresh_from_db()

    def test_normalize_already_resolved(self):
        self.claim.status = HardClaim.Status.CONFIRMED
        with self.assertRaisesMessage(ResolutionError, "Claim is already resolved."):
            normalize_claim_for_resolution(self.claim)
            
    def test_normalize_not_due(self):
        self.claim.until = date.today() + timedelta(days=1)
        with self.assertRaisesMessage(ResolutionError, "Claim cannot be resolved before its due date."):
            normalize_claim_for_resolution(self.claim)

    def test_normalize_missing_provider_symbol(self):
        self.asset.provider_symbol = ""
        self.asset.save()
        with self.assertRaisesMessage(ResolutionError, "Asset is missing provider lookup metadata."):
            normalize_claim_for_resolution(self.claim)

    def test_evaluate_claim_bullish_confirmed(self):
        req = normalize_claim_for_resolution(self.claim)
        result = evaluate_claim(req, 100.0, "http://ref.url", 115.0, "http://due.url")
        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)
        self.assertEqual(result["computed_change_pct"], 15.0)

    def test_evaluate_claim_bullish_rejected(self):
        req = normalize_claim_for_resolution(self.claim)
        # 5% increase is less than 10% threshold
        result = evaluate_claim(req, 100.0, "http://ref.url", 105.0, "http://due.url")
        self.assertEqual(result["status"], HardClaim.Status.REJECTED)

    def test_evaluate_claim_bearish_confirmed(self):
        self.claim.direction = "bearish"
        self.claim.save()
        req = normalize_claim_for_resolution(self.claim)
        # Wait: change = (85 - 100) / 100 = -15%. Target is bearish 10%. -15 <= -10 is True.
        result = evaluate_claim(req, 100.0, "http://ref.url", 85.0, "http://due.url")
        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)
        self.assertEqual(result["computed_change_pct"], -15.0)

    def test_evaluate_claim_bearish_rejected(self):
        self.claim.direction = "bearish"
        self.claim.save()
        req = normalize_claim_for_resolution(self.claim)
        # -5% does not meet strictly -10% or more drop.
        result = evaluate_claim(req, 100.0, "http://ref.url", 95.0, "http://due.url")
        self.assertEqual(result["status"], HardClaim.Status.REJECTED)

    @patch("posts.resolution.fetch_due_price")
    @patch("posts.resolution.fetch_reference_price")
    def test_resolve_hard_claim_success_logging(self, mock_ref, mock_due):
        mock_ref.return_value = (1000.0, "http://mock.ref")
        mock_due.return_value = (1100.0, "http://mock.due")

        result = resolve_hard_claim(self.claim)
        
        # 1100/1000 => 10% change. Target is 10.0%, so exactly CONFIRMED
        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)
        
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, HardClaim.Status.CONFIRMED)

        # Ensure correct insertion of the event log
        events = self.claim.events.all()
        self.assertEqual(events.count(), 1)
        evt = events.last()
        self.assertEqual(evt.event_type, HardClaimEvent.EventType.RESOLUTION)
        self.assertEqual(evt.details["computed_change_pct"], 10.0)
        self.assertEqual(evt.details["prices"]["reference_url"], "http://mock.ref")
        self.assertEqual(evt.details["prices"]["due_url"], "http://mock.due")
