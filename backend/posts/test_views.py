import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from posts.models import Asset, Post, HardClaim, OHLCData
from accounts.models import WalletUser


class HardClaimChartDataViewTests(TestCase):
    def setUp(self):
        # The TestCase class inherently wraps everything in a transaction 
        # and rolls it back, effectively acting as an isolated mock database.
        self.client = Client()

        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.BINANCE,
            provider_symbol="bitcoin",
            quote_currency="USD",
            binance_symbol="BTCUSDT"
        )
        self.author = WalletUser.objects.create(address="0x123")
        self.post = Post.objects.create(
            author=self.author,
            content="To the moon!"
        )
        
        now = timezone.now()
        
        # Create a hard claim
        self.claim = HardClaim.objects.create(
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage="10.00",
            until=(now + timedelta(days=5)).date(),
            status=HardClaim.Status.UNDETERMINED,
        )
        
        # Seed an OHLCData point to test serialization
        # The timestamp should be at exactly midnight to simulate a daily candle
        # 5-day window → default 15m (< 1 week)
        self.candle_timestamp = now.replace(hour=0, minute=0, second=0, microsecond=0)
        OHLCData.objects.create(
            asset=self.asset,
            timestamp=self.candle_timestamp,
            interval="15m",
            open=1000.0,
            high=1100.0,
            low=900.0,
            close=1050.0
        )

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.get_ohlc_data")
    def test_hardclaim_chart_data_serialization_success(self, mock_get_ohlc, mock_ref):
        """
        Ensures that the chart data endpoint returns a valid 200 JSON response and
        correctly serializes the OHLCData timestamps.
        """
        mock_ref.return_value = (1000.0, "http://mock.ref")
        mock_get_ohlc.return_value = list(OHLCData.objects.filter(asset=self.asset))

        # Make the request
        url = reverse("hard-claim-chart-data", kwargs={"pk": self.claim.id})
        response = self.client.get(url)

        # Assert successful 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Parse response
        data = response.json()
        
        # Assert chart data structure
        self.assertIn("ohlc", data)
        self.assertIsInstance(data["ohlc"], list)
        
        # Verify the seeded candle was correctly serialized
        self.assertEqual(data["interval"], "15m")
        self.assertEqual(data["default_interval"], "15m")
        self.assertEqual(len(data["ohlc"]), 1)
        candle = data["ohlc"][0]
        
        # Crucial assertion: the date property maps to row.timestamp.isoformat()
        self.assertEqual(candle["date"], self.candle_timestamp.isoformat())
        self.assertEqual(float(candle["open"]), 1000.0)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.get_ohlc_data")
    def test_hardclaim_chart_data_price_value_type(self, mock_get_ohlc, mock_ref):
        """
        Ensures that if value_type is PRICE, the target_price returned is exactly the
        absolute value stored in percentage.
        """
        self.claim.value_type = "PRICE"
        self.claim.percentage = 1500.0
        self.claim.save()

        mock_ref.return_value = (1000.0, "http://mock.ref")
        mock_get_ohlc.return_value = list(OHLCData.objects.filter(asset=self.asset))

        url = reverse("hard-claim-chart-data", kwargs={"pk": self.claim.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["target_price"], 1500.0)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.get_ohlc_data")
    def test_short_claim_window_uses_15m_interval(self, mock_get_ohlc, mock_ref):
        from posts.ohlc_fetcher import Interval

        mock_ref.return_value = (1000.0, "http://mock.ref")
        mock_get_ohlc.return_value = []
        self.claim.until = (timezone.now() + timedelta(days=1)).date()
        self.claim.save()

        url = reverse("hard-claim-chart-data", kwargs={"pk": self.claim.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["interval"], "15m")
        self.assertEqual(data["default_interval"], "15m")
        mock_get_ohlc.assert_called_once()
        self.assertEqual(mock_get_ohlc.call_args.kwargs["interval"], Interval.FIFTEEN_MIN)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.get_ohlc_data")
    def test_medium_claim_window_defaults_to_4h(self, mock_get_ohlc, mock_ref):
        from posts.ohlc_fetcher import Interval

        mock_ref.return_value = (1000.0, "http://mock.ref")
        mock_get_ohlc.return_value = []
        self.claim.until = (timezone.now() + timedelta(days=14)).date()
        self.claim.save()

        response = self.client.get(reverse("hard-claim-chart-data", kwargs={"pk": self.claim.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["interval"], "4h")
        self.assertEqual(data["default_interval"], "4h")
        self.assertEqual(mock_get_ohlc.call_args.kwargs["interval"], Interval.FOUR_HOUR)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.get_ohlc_data")
    def test_long_claim_window_defaults_to_1d(self, mock_get_ohlc, mock_ref):
        from posts.ohlc_fetcher import Interval

        mock_ref.return_value = (1000.0, "http://mock.ref")
        mock_get_ohlc.return_value = []
        self.claim.until = (timezone.now() + timedelta(days=45)).date()
        self.claim.save()

        response = self.client.get(reverse("hard-claim-chart-data", kwargs={"pk": self.claim.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["interval"], "1d")
        self.assertEqual(data["default_interval"], "1d")
        self.assertEqual(mock_get_ohlc.call_args.kwargs["interval"], Interval.ONE_DAY)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.get_ohlc_data")
    def test_chart_interval_query_param_override(self, mock_get_ohlc, mock_ref):
        from posts.ohlc_fetcher import Interval

        mock_ref.return_value = (1000.0, "http://mock.ref")
        mock_get_ohlc.return_value = []

        url = reverse("hard-claim-chart-data", kwargs={"pk": self.claim.id})
        response = self.client.get(url, {"interval": "1d"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["interval"], "1d")
        self.assertEqual(data["default_interval"], "15m")
        self.assertEqual(mock_get_ohlc.call_args.kwargs["interval"], Interval.ONE_DAY)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.get_ohlc_data")
    def test_invalid_chart_interval_returns_400(self, mock_get_ohlc, mock_ref):
        mock_ref.return_value = (1000.0, "http://mock.ref")
        url = reverse("hard-claim-chart-data", kwargs={"pk": self.claim.id})
        response = self.client.get(url, {"interval": "1m"})
        self.assertEqual(response.status_code, 400)
        mock_get_ohlc.assert_not_called()

class PostCreationAtomicTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = WalletUser.objects.create(address="0xatomic", energy=4, rep=100)
        self.asset = Asset.objects.create(
            symbol="ETH",
            name="Ethereum",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.BINANCE,
            provider_symbol="ethereum",
            quote_currency="USD",
            binance_symbol="ETHUSDT"
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken()
        refresh["address"] = self.author.address
        self.token = str(refresh.access_token)

    def test_post_with_hard_claims_insufficient_energy_rolls_back(self):
        """
        If a user has 4 energy, creating 3 market-backed claims (costing 6 energy total)
        should fail entirely. The Post should NOT be created, no HardClaims should be created,
        and energy should remain at 4.
        """
        initial_post_count = Post.objects.count()
        initial_claim_count = HardClaim.objects.count()

        payload = {
            "content": "Ethereum going to 10k!",
            "claims": [],
            "hard_claims": [
                {
                    "asset_id": self.asset.id,
                    "direction": "Bullish",
                    "percentage": 10.0,
                    "until": (timezone.now() + timedelta(days=2)).date().isoformat(),
                    "market": {"side": "YES", "stake_rep": 10}
                },
                {
                    "asset_id": self.asset.id,
                    "direction": "Bullish",
                    "percentage": 20.0,
                    "until": (timezone.now() + timedelta(days=3)).date().isoformat(),
                    "market": {"side": "YES", "stake_rep": 10}
                },
                {
                    "asset_id": self.asset.id,
                    "direction": "Bullish",
                    "percentage": 30.0,
                    "until": (timezone.now() + timedelta(days=4)).date().isoformat(),
                    "market": {"side": "YES", "stake_rep": 10}
                }
            ]
        }
        
        response = self.client.post(
            reverse("post-list-create"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        
        # Should fail with 400
        self.assertEqual(response.status_code, 400)
        
        # Verify rollbacks
        self.assertEqual(Post.objects.count(), initial_post_count)
        self.assertEqual(HardClaim.objects.count(), initial_claim_count)
        
        # Energy should be unmodified
        self.author.refresh_from_db()
        self.assertEqual(self.author.energy, 4)

