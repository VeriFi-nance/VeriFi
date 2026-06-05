from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from posts.models import Asset, Post, HardClaim, HardClaimEvent, OHLCData
from posts.resolution import (
    normalize_claim_for_resolution,
    preview_resolution,
    resolve_hard_claim,
    ResolutionError,
)
from posts.ohlc_fetcher import OHLCFetchError

from accounts.models import WalletUser
from django.utils import timezone

class ResolutionTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.BINANCE,
            provider_symbol="bitcoin",
            quote_currency="USD",
            binance_symbol="BTCUSDT",
            kucoin_symbol="BTC-USDT",
            kraken_pair="XBTUSD",
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
            until=(timezone.now() + timedelta(days=1)).date(), # initially future to pass create
            status=HardClaim.Status.UNDETERMINED,
        )
        # Backdate so it counts as due
        HardClaim.objects.filter(id=self.claim.id).update(
            created_at=timezone.now() - timedelta(days=5),
            until=(timezone.now() - timedelta(days=2)).date()
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

    def test_normalize_unsupported_direction(self):
        self.claim.direction = "sideways"
        self.claim.value_type = ""
        self.claim.save()
        with self.assertRaisesMessage(ResolutionError, "Only bullish and bearish"):
            normalize_claim_for_resolution(self.claim)

    def test_normalize_derives_direction_from_value_type(self):
        self.claim.direction = ""
        self.claim.value_type = "PERCENTAGE_DOWN"
        self.claim.save()
        payload = normalize_claim_for_resolution(self.claim)
        self.assertEqual(payload["target"]["direction"], "bearish")

    @patch("posts.resolution.get_ohlc_data")
    @patch("posts.resolution.fetch_reference_price")
    def test_preview_resolution_maps_ohlc_fetch_error(self, mock_ref, mock_ohlc):
        mock_ref.return_value = (1000.0, "http://mock.ref")
        mock_ohlc.side_effect = OHLCFetchError("all sources failed")
        with self.assertRaises(ResolutionError) as ctx:
            preview_resolution(self.claim)
        self.assertEqual(ctx.exception.code, "NO_OHLC_DATA")

    def _seed_ohlc(self, base_price=1000.0, days=5, trend_pct=2.0):
        """Create OHLC rows for the claim period with a simple uptrend."""
        start = self.claim.created_at.date()
        rows = []
        for i in range(days):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = base_price * (1 + trend_pct * i / 100)
            rows.append(OHLCData(
                asset=self.asset,
                timestamp=d,
                open=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price * 1.01,
            ))
        OHLCData.objects.bulk_create(rows)
        return rows

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_bullish_confirmed(self, mock_ohlc_fetch, mock_ref):
        """If OHLC high reaches target, claim is confirmed."""
        mock_ref.return_value = (1000.0, "http://mock.ref")
        # Seed OHLC where high on day 4 exceeds 10% target (1100)
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 + i * 30  # 1000, 1030, 1060, 1090, 1120
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 20, low=price - 20, close=price + 10,
            )
        mock_ohlc_fetch.return_value = []  # Already in DB, won't be called

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)
        self.assertGreater(len(result["hit_days"]), 0)
        self.assertIsNotNone(result["target_reached_at"])

        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, HardClaim.Status.CONFIRMED)

        events = self.claim.events.all()
        self.assertEqual(events.count(), 1)
        evt = events.last()
        self.assertEqual(evt.event_type, HardClaimEvent.EventType.RESOLUTION)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_bullish_rejected(self, mock_ohlc_fetch, mock_ref):
        """If OHLC high never reaches 10% target, claim is rejected."""
        mock_ref.return_value = (1000.0, "http://mock.ref")
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 + i * 10  # 1000, 1010, 1020, 1030, 1040 — max high = 1060
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 20, low=price - 20, close=price + 5,
            )
        mock_ohlc_fetch.return_value = []

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.REJECTED)
        self.assertEqual(len(result["hit_days"]), 0)
        self.assertIsNone(result["target_reached_at"])
        # Closest price should exist
        self.assertIsNotNone(result["prices"]["closest"])

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_bearish_confirmed(self, mock_ohlc_fetch, mock_ref):
        """Bearish claim: low goes below target → confirmed."""
        self.claim.direction = "bearish"
        self.claim.value_type = "PERCENTAGE_DOWN"
        self.claim.save()
        mock_ref.return_value = (1000.0, "http://mock.ref")
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 - i * 30  # 1000, 970, 940, 910, 880
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 10, low=price - 20, close=price - 5,
            )
        mock_ohlc_fetch.return_value = []

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)

    def test_normalize_price_claim(self):
        self.claim.value_type = "PRICE"
        self.claim.percentage = 1500.0
        self.claim.save()
        payload = normalize_claim_for_resolution(self.claim)
        self.assertEqual(payload["target"]["kind"], "price")
        self.assertEqual(payload["target"]["value"], 1500.0)
        self.assertEqual(payload["target"]["unit"], "USD")

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_price_bullish_confirmed(self, mock_ohlc_fetch, mock_ref):
        self.claim.value_type = "PRICE"
        self.claim.percentage = 1100.0
        self.claim.save()
        mock_ref.return_value = (1000.0, "http://mock.ref")
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 + i * 30
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 20, low=price - 20, close=price + 10,
            )
        mock_ohlc_fetch.return_value = []

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)
        self.assertEqual(result["prices"]["target"], 1100.0)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_price_bullish_rejected(self, mock_ohlc_fetch, mock_ref):
        self.claim.value_type = "PRICE"
        self.claim.percentage = 1200.0
        self.claim.save()
        mock_ref.return_value = (1000.0, "http://mock.ref")
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 + i * 10
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 20, low=price - 20, close=price + 5,
            )
        mock_ohlc_fetch.return_value = []

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.REJECTED)
        self.assertEqual(result["prices"]["target"], 1200.0)


class ResolveClaimsCommandTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.BINANCE,
            provider_symbol="bitcoin",
            quote_currency="USD",
            binance_symbol="BTCUSDT",
        )
        self.author = WalletUser.objects.create(address="0xabc")
        self.post = Post.objects.create(author=self.author, content="test")

    def test_due_claims_excludes_until_today(self):
        from posts.management.commands.resolve_claims import due_claims_queryset

        today_claim = HardClaim.objects.create(
            author=self.author,
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage=5.0,
            until=date.today() + timedelta(days=1),
            status=HardClaim.Status.UNDETERMINED,
        )
        past = HardClaim.objects.create(
            author=self.author,
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage=5.0,
            until=date.today() + timedelta(days=1),
            status=HardClaim.Status.UNDETERMINED,
        )
        HardClaim.objects.filter(id=today_claim.id).update(
            created_at=timezone.now() - timedelta(days=5),
            until=date.today(),
        )
        HardClaim.objects.filter(id=past.id).update(
            created_at=timezone.now() - timedelta(days=5),
            until=date.today() - timedelta(days=1),
        )
        due_ids = list(due_claims_queryset().values_list("id", flat=True))
        self.assertEqual(due_ids, [past.id])

