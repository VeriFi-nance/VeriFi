import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from posts.models import (
    Asset,
    Post,
    HardClaim,
    HardClaimEvent,
    OHLCData,
    Channel,
    ChannelMembership,
    PostLike,
    PostComment,
    SavedProof,
)
from accounts.models import WalletUser
from . import rep_market


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
            reference_price=1000.0,
            reference_price_url="stored_at_creation",
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

    @patch("posts.ohlc_fetcher.get_ohlc_data")
    def test_chart_uses_stored_reference_over_resolution_event(self, mock_get_ohlc):
        mock_get_ohlc.return_value = list(OHLCData.objects.filter(asset=self.asset))
        self.claim.reference_price = 67507.18
        self.claim.status = HardClaim.Status.CONFIRMED
        self.claim.save()
        HardClaimEvent.objects.create(
            hard_claim=self.claim,
            event_type=HardClaimEvent.EventType.RESOLUTION,
            details={
                "prices": {"reference": 66760.83, "target": 67428.44},
                "hit_days": ["2026-06-02"],
            },
        )

        response = self.client.get(reverse("hard-claim-chart-data", kwargs={"pk": self.claim.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reference_price"], 67507.18)
        self.assertEqual(data["target_price"], 74257.9)

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
        refresh = RefreshToken()
        refresh["address"] = self.author.address
        self.token = str(refresh.access_token)

    def test_post_with_hard_claims_insufficient_energy_rolls_back(self):
        """
        If a user has 2 energy, creating 3 market-backed claims (costing 3 energy total)
        should fail entirely. The Post should NOT be created, no HardClaims should be created,
        and energy should remain at 2.
        """
        initial_post_count = Post.objects.count()
        initial_claim_count = HardClaim.objects.count()
        self.author.energy = 2
        self.author.last_energy_grant = timezone.now()
        self.author.save(update_fields=["energy", "last_energy_grant"])

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
        self.assertEqual(self.author.energy, 2)

    def test_market_buy_does_not_spend_energy(self):
        creator = WalletUser.objects.create(
            address="0x00000000000000000000000000000000000c0dea",
            energy=4,
            rep=100,
            last_energy_grant=timezone.now(),
        )
        trader = WalletUser.objects.create(
            address="0x00000000000000000000000000000000000b0bba",
            energy=3,
            rep=100,
            last_energy_grant=timezone.now(),
        )
        hard_claim = HardClaim.objects.create(
            author=creator,
            asset=self.asset,
            direction="Bullish",
            percentage=10.0,
            until=(timezone.now() + timedelta(days=2)).date(),
        )
        rep_market.init_market(hard_claim, creator, "YES", 10)

        refresh = RefreshToken()
        refresh["address"] = trader.address
        response = self.client.post(
            reverse("hard-claim-market-buy", kwargs={"pk": hard_claim.pk}),
            data=json.dumps({"side": "NO"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        )

        self.assertEqual(response.status_code, 201)
        trader.refresh_from_db()
        self.assertEqual(trader.energy, 3)


class PostSocialActionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = WalletUser.objects.create(address="0xauthor")
        self.viewer = WalletUser.objects.create(address="0xviewer")
        self.other = WalletUser.objects.create(address="0xother")
        self.post = Post.objects.create(author=self.author, content="Social proof")
        self.viewer_token = self._token(self.viewer)
        self.other_token = self._token(self.other)

    def _token(self, user):
        refresh = RefreshToken()
        refresh["address"] = user.address
        return str(refresh.access_token)

    def _auth(self, token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self.viewer_token}"}

    def test_public_feed_includes_social_counts_for_anonymous_users(self):
        PostLike.objects.create(post=self.post, user=self.viewer)
        PostComment.objects.create(post=self.post, author=self.viewer, content="I agree")
        SavedProof.objects.create(post=self.post, user=self.viewer)

        response = self.client.get(reverse("post-list-create"))

        self.assertEqual(response.status_code, 200)
        post = response.json()["results"][0]
        self.assertEqual(post["like_count"], 1)
        self.assertEqual(post["comment_count"], 1)
        self.assertEqual(post["saved_proof_count"], 1)
        self.assertFalse(post["liked_by_me"])
        self.assertFalse(post["saved_proof_by_me"])

    def test_post_detail_includes_current_user_social_state(self):
        PostLike.objects.create(post=self.post, user=self.viewer)
        SavedProof.objects.create(post=self.post, user=self.viewer)

        response = self.client.get(reverse("post-detail", kwargs={"pk": self.post.pk}), **self._auth())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["like_count"], 1)
        self.assertEqual(data["saved_proof_count"], 1)
        self.assertTrue(data["liked_by_me"])
        self.assertTrue(data["saved_proof_by_me"])

    def test_like_requires_auth_and_is_idempotent(self):
        url = reverse("post-like", kwargs={"pk": self.post.pk})

        self.assertEqual(self.client.post(url).status_code, 401)
        first = self.client.post(url, **self._auth())
        second = self.client.post(url, **self._auth())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(PostLike.objects.filter(post=self.post, user=self.viewer).count(), 1)
        self.assertEqual(second.json()["like_count"], 1)
        self.assertTrue(second.json()["liked_by_me"])

        deleted = self.client.delete(url, **self._auth())
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(PostLike.objects.filter(post=self.post, user=self.viewer).count(), 0)
        self.assertFalse(deleted.json()["liked_by_me"])

    def test_saved_proof_requires_auth_and_is_idempotent(self):
        url = reverse("post-save-proof", kwargs={"pk": self.post.pk})

        self.assertEqual(self.client.post(url).status_code, 401)
        first = self.client.post(url, **self._auth())
        second = self.client.post(url, **self._auth())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(SavedProof.objects.filter(post=self.post, user=self.viewer).count(), 1)
        self.assertEqual(second.json()["saved_proof_count"], 1)
        self.assertTrue(second.json()["saved_proof_by_me"])

        deleted = self.client.delete(url, **self._auth())
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(SavedProof.objects.filter(post=self.post, user=self.viewer).count(), 0)
        self.assertFalse(deleted.json()["saved_proof_by_me"])

    def test_comments_require_auth_for_creation_and_validate_content(self):
        url = reverse("post-comments", kwargs={"pk": self.post.pk})

        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, data=json.dumps({"content": "Hi"}), content_type="application/json").status_code, 401)

        blank = self.client.post(
            url,
            data=json.dumps({"content": "   "}),
            content_type="application/json",
            **self._auth(),
        )
        too_long = self.client.post(
            url,
            data=json.dumps({"content": "x" * 501}),
            content_type="application/json",
            **self._auth(),
        )
        created = self.client.post(
            url,
            data=json.dumps({"content": "First comment"}),
            content_type="application/json",
            **self._auth(),
        )

        self.assertEqual(blank.status_code, 400)
        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["content"], "First comment")
        self.assertEqual(PostComment.objects.filter(post=self.post).count(), 1)

    def test_private_channel_social_endpoints_require_membership(self):
        channel = Channel.objects.create(name="Alpha", creator=self.author)
        private_post = Post.objects.create(author=self.author, content="Members only", channel=channel)

        like_url = reverse("post-like", kwargs={"pk": private_post.pk})
        comments_url = reverse("post-comments", kwargs={"pk": private_post.pk})
        save_url = reverse("post-save-proof", kwargs={"pk": private_post.pk})

        self.assertEqual(self.client.post(like_url, **self._auth()).status_code, 403)
        self.assertEqual(self.client.get(comments_url, **self._auth()).status_code, 403)
        self.assertEqual(
            self.client.post(
                comments_url,
                data=json.dumps({"content": "Nope"}),
                content_type="application/json",
                **self._auth(),
            ).status_code,
            403,
        )
        self.assertEqual(self.client.post(save_url, **self._auth()).status_code, 403)

        ChannelMembership.objects.create(
            channel=channel,
            user=self.viewer,
            status=ChannelMembership.Status.APPROVED,
        )

        self.assertEqual(self.client.post(like_url, **self._auth()).status_code, 200)
        self.assertEqual(self.client.get(comments_url, **self._auth()).status_code, 200)
        self.assertEqual(self.client.post(save_url, **self._auth()).status_code, 200)
