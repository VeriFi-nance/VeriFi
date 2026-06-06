from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import WalletUser
from .models import Post, Asset, HardClaim, ChannelMembership
from .resolution import ResolutionError, normalize_claim_for_resolution


class HardClaimAPITestCase(APITestCase):
    def setUp(self):
        """Set up test data before each test method."""
        # Create a test wallet user (lowercase address, matching production flow)
        self.wallet_user = WalletUser.objects.create(
            address="0x742d35cc6634c0532925a3b844bc454e4438f44e"
        )
        
        # Create a test asset
        self.asset = Asset.objects.create(
            name="Bitcoin",
            symbol="BTC",
            description="Digital gold",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.COINGECKO,
            provider_symbol="bitcoin",
        )
        
        # Create JWT token for authentication
        self.token = self._get_jwt_token(self.wallet_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def _get_jwt_token(self, user):
        """Helper method to generate JWT token for a user."""
        refresh = RefreshToken()
        refresh["address"] = user.address
        return str(refresh.access_token)

    @patch('posts.views.verify_claim_signature')
    def test_create_hard_claim_success(self, mock_verify):
        """Test successfully creating a hard claim."""
        url = reverse('hard-claims')
        data = {
            'asset_id': self.asset.id,
            'direction': 'bullish',
            'percentage': 25.0,
            'until': '2027-12-31',
            'status': 'undetermined',
            'signature': '0x123',
            'claim_payload': {
                'asset_symbol': 'BTC',
                'author_username': self.wallet_user.username,
                'direction': 'bullish',
                'percentage': 25.0,
                'until': '2027-12-31',
                'created_at': timezone.now().isoformat(),
            },
        }

        response = self.client.post(url, data, format='json')

        # Assert response status
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Assert response data contains expected fields
        self.assertIn('id', response.data)
        self.assertIn('author_address', response.data)
        self.assertIn('asset', response.data)
        self.assertIn('direction', response.data)
        self.assertIn('percentage', response.data)
        self.assertIn('until', response.data)
        self.assertIn('status', response.data)

        # Assert response values
        self.assertEqual(response.data['direction'], 'bullish')
        self.assertEqual(response.data['percentage'], 25.0)
        self.assertEqual(response.data['until'], '2027-12-31')
        self.assertEqual(response.data['status'], 'undetermined')
        self.assertEqual(response.data['author_address'], self.wallet_user.address)

        # Assert the hard claim was created in the database with correct author
        hard_claim = HardClaim.objects.get(id=response.data['id'])
        self.assertEqual(hard_claim.author, self.wallet_user)
        self.assertEqual(hard_claim.asset, self.asset)
        self.assertEqual(hard_claim.direction, 'bullish')
        self.assertEqual(hard_claim.percentage, 25.0)
        self.assertEqual(str(hard_claim.until), '2027-12-31')
        self.assertEqual(hard_claim.status, 'undetermined')

    def test_create_hard_claim_invalid_data(self):
        """Test creating a hard claim with invalid data."""
        url = reverse('hard-claims')
        data = {
            'text': 'Invalid claim',
            'asset_id': 9999,  # Non-existent asset ID
            'percentage': 10.0,
            'until': '2027-12-31'
        }
        
        response = self.client.post(url, data, format='json')
        
        # Should return 400 Bad Request due to invalid asset_id
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_hard_claim_missing_required_fields(self):
        """Test creating a hard claim with missing required fields."""
        url = reverse('hard-claims')
        data = {
            'text': 'Missing required fields',
            'asset_id': self.asset.id
            # Missing `until`
        }
        
        response = self.client.post(url, data, format='json')
        
        # Should return 400 Bad Request due to missing required fields
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_hard_claim_unauthenticated(self):
        """Test that unauthenticated users cannot create hard claims."""
        # Clear credentials to simulate unauthenticated request
        self.client.credentials()
        
        url = reverse('hard-claims')
        data = {
            'asset_id': self.asset.id,
            'direction': 'bullish',
            'percentage': 25.0,
            'until': '2027-12-31'
        }

        response = self.client.post(url, data, format='json')

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)


class HardClaimUpdateStatusTestCase(APITestCase):
    def setUp(self):
        self.admin_address = "0xadmin000000000000000000000000000000000000"
        self.regular_address = "0x742d35cc6634c0532925a3b844bc454e4438f44e"

        self.admin_user = WalletUser.objects.create(address=self.admin_address)
        self.regular_user = WalletUser.objects.create(address=self.regular_address)

        self.asset = Asset.objects.create(
            name="Bitcoin",
            symbol="BTC",
            description="Digital gold",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.COINGECKO,
            provider_symbol="bitcoin",
        )
        self.hard_claim = HardClaim.objects.create(
            author=self.regular_user,
            asset=self.asset,
            direction="bullish",
            percentage=20.0,
            until="2027-12-31",
            status="undetermined",
        )

    def _auth(self, user):
        refresh = RefreshToken()
        refresh["address"] = user.address
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

    def _url(self):
        return reverse("hard-claim-update-status", kwargs={"pk": self.hard_claim.pk})

    def test_admin_can_update_status(self):
        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.patch(self._url(), {"status": "confirmed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")
        self.hard_claim.refresh_from_db()
        self.assertEqual(self.hard_claim.status, "confirmed")

    def test_non_admin_is_forbidden(self):
        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.regular_user)
            response = self.client.patch(self._url(), {"status": "confirmed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_rejected(self):
        self.client.credentials()
        response = self.client.patch(self._url(), {"status": "confirmed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_status_is_rejected(self):
        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.patch(self._url(), {"status": "invalid_value"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_hard_claim_returns_404(self):
        url = reverse("hard-claim-update-status", kwargs={"pk": 99999})
        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.patch(url, {"status": "confirmed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class HardClaimResolutionContractTestCase(APITestCase):
    def setUp(self):
        self.user = WalletUser.objects.create(
            address="0x742d35cc6634c0532925a3b844bc454e4438f44e"
        )
        self.asset = Asset.objects.create(
            name="Bitcoin",
            symbol="BTC",
            description="Digital gold",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.COINGECKO,
            provider_symbol="bitcoin",
        )

    def test_normalize_claim_for_resolution_uses_asset_metadata(self):
        created_at = timezone.now() - timedelta(days=10)
        due_date = (timezone.now() - timedelta(days=1)).date()
        hard_claim = HardClaim.objects.create(
            author=self.user,
            asset=self.asset,
            direction="bullish",
            percentage=10.0,
            until=(timezone.now() + timedelta(days=10)).date(),
            status="undetermined",
        )
        HardClaim.objects.filter(pk=hard_claim.pk).update(created_at=created_at, until=due_date)
        hard_claim.refresh_from_db()

        payload = normalize_claim_for_resolution(hard_claim)

        self.assertEqual(payload["version"], "1.0")
        self.assertEqual(payload["instrument"]["provider"], "coingecko")
        self.assertEqual(payload["instrument"]["provider_symbol"], "bitcoin")
        self.assertEqual(payload["instrument"]["market_type"], "crypto")
        self.assertEqual(payload["target"]["kind"], "percentage")
        self.assertEqual(payload["target"]["value"], 10.0)
        self.assertEqual(payload["target"]["direction"], "bullish")

    def test_missing_provider_symbol_bubbles_no_price_data(self):
        self.asset.provider_symbol = ""
        self.asset.save(update_fields=["provider_symbol"])
        created_at = timezone.now() - timedelta(days=10)
        due_date = (timezone.now() - timedelta(days=1)).date()
        hard_claim = HardClaim.objects.create(
            author=self.user,
            asset=self.asset,
            direction="bullish",
            percentage=10.0,
            until=(timezone.now() + timedelta(days=10)).date(),
            status="undetermined",
        )
        HardClaim.objects.filter(pk=hard_claim.pk).update(created_at=created_at, until=due_date)
        hard_claim.refresh_from_db()

        with self.assertRaises(ResolutionError) as ctx:
            from posts.resolution import fetch_reference_price
            fetch_reference_price(hard_claim)

        self.assertEqual(ctx.exception.code, "PROVIDER_NO_PRICE_DATA")


class HardClaimResolveApiTestCase(APITestCase):
    def setUp(self):
        self.admin_address = "0xadmin000000000000000000000000000000000000"
        self.regular_address = "0x742d35cc6634c0532925a3b844bc454e4438f44e"

        self.admin_user = WalletUser.objects.create(address=self.admin_address)
        self.regular_user = WalletUser.objects.create(address=self.regular_address)

        self.crypto_asset = Asset.objects.create(
            name="Bitcoin",
            symbol="BTC",
            description="Digital gold",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.COINGECKO,
            provider_symbol="bitcoin",
        )
        self.forex_asset = Asset.objects.create(
            name="Euro / US Dollar",
            symbol="EURUSD",
            description="FX pair",
            market_type=Asset.MarketType.FOREX,
            provider=Asset.Provider.YFINANCE,
            provider_symbol="EURUSD=X",
        )

    def _auth(self, user):
        refresh = RefreshToken()
        refresh["address"] = user.address
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

    def _make_claim(self, *, asset, direction="bullish", percentage=10.0, status="undetermined", days_past_due=1):
        created_at = timezone.now() - timedelta(days=14)
        due_date = (timezone.now() - timedelta(days=days_past_due)).date()
        hard_claim = HardClaim.objects.create(
            author=self.regular_user,
            asset=asset,
            direction=direction,
            percentage=percentage,
            until=(timezone.now() + timedelta(days=10)).date(),
            status=status,
        )
        HardClaim.objects.filter(pk=hard_claim.pk).update(
            created_at=created_at,
            until=due_date,
        )
        hard_claim.refresh_from_db()
        return hard_claim

    def _url(self, claim):
        return reverse("hard-claim-resolve", kwargs={"pk": claim.pk})

    @patch("posts.views.resolve_hard_claim")
    def test_admin_can_resolve_past_due_bullish_claim(self, mock_resolve):
        claim = self._make_claim(asset=self.crypto_asset, direction="bullish", percentage=10.0)
        mock_resolve.return_value = {
            "version": "1.0",
            "claim_id": claim.id,
            "resolvable": True,
            "resolved": True,
            "status": "confirmed",
            "instrument": {"symbol": "BTC", "provider": "coingecko", "provider_symbol": "bitcoin"},
            "target": {"kind": "percentage", "direction": "bullish", "value": 10.0, "unit": "percent"},
            "prices": {"reference": 70000.0, "peak": 78100.0, "currency": "USD"},
            "computed_change_pct": 11.57,
            "evaluation_reason": "peak price met or exceeded bullish percentage target within timeframe",
            "resolved_at": "2026-05-01T09:00:00Z",
        }

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")
        mock_resolve.assert_called_once()

    @patch("posts.resolution.get_ohlc_data")
    @patch("posts.resolution.fetch_reference_price")
    def test_actual_resolution_persists_status_and_returns_computed_payload(self, mock_ref, mock_ohlc):
        claim = self._make_claim(asset=self.crypto_asset, direction="bullish", percentage=10.0)
        mock_ref.return_value = (70000.0, "http://mock.ref")
        from posts.models import OHLCData
        mock_ohlc.return_value = [
            OHLCData(asset=self.crypto_asset, timestamp=claim.created_at, interval="1d", open=70000.0, high=78100.0, low=69000.0, close=75000.0)
        ]

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")
        self.assertEqual(response.data["prices"]["reference"], 70000.0)
        self.assertEqual(response.data["prices"]["peak"], 78100.0)
        self.assertAlmostEqual(response.data["computed_change_pct"], 11.57, places=2)
        claim.refresh_from_db()
        self.assertEqual(claim.status, "confirmed")

    @patch("posts.views.resolve_hard_claim")
    def test_admin_can_resolve_past_due_bearish_claim(self, mock_resolve):
        claim = self._make_claim(asset=self.crypto_asset, direction="bearish", percentage=12.0)
        mock_resolve.return_value = {
            "version": "1.0",
            "claim_id": claim.id,
            "resolvable": True,
            "resolved": True,
            "status": "confirmed",
            "instrument": {"symbol": "BTC", "provider": "coingecko", "provider_symbol": "bitcoin"},
            "target": {"kind": "percentage", "direction": "bearish", "value": 12.0, "unit": "percent"},
            "prices": {"reference": 70000.0, "peak": 60000.0, "currency": "USD"},
            "computed_change_pct": -14.29,
            "evaluation_reason": "trough price met or exceeded bearish percentage target within timeframe",
            "resolved_at": "2026-05-01T09:00:00Z",
        }

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")

    @patch("posts.views.resolve_hard_claim")
    def test_resolve_returns_rejected_when_target_missed(self, mock_resolve):
        claim = self._make_claim(asset=self.crypto_asset, direction="bullish", percentage=25.0)
        mock_resolve.return_value = {
            "version": "1.0",
            "claim_id": claim.id,
            "resolvable": True,
            "resolved": True,
            "status": "rejected",
            "instrument": {"symbol": "BTC", "provider": "coingecko", "provider_symbol": "bitcoin"},
            "target": {"kind": "percentage", "direction": "bullish", "value": 25.0, "unit": "percent"},
            "prices": {"reference": 70000.0, "peak": 74000.0, "currency": "USD"},
            "computed_change_pct": 5.71,
            "evaluation_reason": "peak price did not reach bullish percentage target within timeframe",
            "resolved_at": "2026-05-01T09:00:00Z",
        }

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "rejected")

    def test_resolve_rejects_before_due_date(self):
        claim = HardClaim.objects.create(
            author=self.regular_user,
            asset=self.crypto_asset,
            direction="bullish",
            percentage=10.0,
            until=(timezone.now() + timedelta(days=3)).date(),
            status="undetermined",
        )

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error_code"], "CLAIM_NOT_DUE")

    def test_resolve_rejects_already_resolved_claim(self):
        claim = self._make_claim(asset=self.crypto_asset, status="confirmed")

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error_code"], "CLAIM_ALREADY_RESOLVED")

    def test_non_admin_is_rejected(self):
        claim = self._make_claim(asset=self.crypto_asset)

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.regular_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("posts.views.resolve_hard_claim")
    def test_provider_failure_does_not_mutate_claim_status(self, mock_resolve):
        claim = self._make_claim(asset=self.crypto_asset)
        mock_resolve.side_effect = ResolutionError(
            "PROVIDER_NETWORK_ERROR",
            "Provider network request failed.",
        )

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        claim.refresh_from_db()
        self.assertEqual(claim.status, "undetermined")
        self.assertEqual(response.data["error_code"], "PROVIDER_NETWORK_ERROR")

    def test_unsupported_provider_metadata_returns_error(self):
        broken_asset = Asset.objects.create(
            name="Broken",
            symbol="BRK",
            description="Broken asset",
            market_type=Asset.MarketType.EQUITY,
            provider="unsupported",
            provider_symbol="BRK",
        )
        claim = self._make_claim(asset=broken_asset)

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error_code"], "NO_OHLC_DATA")

    @patch("posts.resolution._fetch_coingecko_price")
    def test_coingecko_provider_is_used_for_crypto(self, mock_price):
        claim = self._make_claim(asset=self.crypto_asset)
        mock_price.return_value = (70000.0, "http://mock")

        from posts.resolution import fetch_current_price
        reference_price, _ = fetch_current_price(claim.asset, claim.created_at)

        self.assertEqual(reference_price, 70000.0)
        mock_price.assert_called_once()

    @patch("posts.resolution._fetch_yfinance_price")
    def test_yfinance_provider_is_used_for_non_crypto(self, mock_price):
        claim = self._make_claim(asset=self.forex_asset)
        mock_price.return_value = (1.12, "http://mock")

        from posts.resolution import fetch_current_price
        reference_price, _ = fetch_current_price(claim.asset, claim.created_at)

        self.assertEqual(reference_price, 1.12)
        mock_price.assert_called_once()

    @patch("posts.views.resolve_hard_claim")
    def test_malformed_provider_response_bubbles_as_structured_error(self, mock_resolve):
        claim = self._make_claim(asset=self.forex_asset)
        mock_resolve.side_effect = ResolutionError(
            "PROVIDER_INVALID_JSON",
            "Provider returned malformed JSON.",
        )

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error_code"], "PROVIDER_INVALID_JSON")

class ChannelPostPermissionTestCase(APITestCase):
    def setUp(self):
        self.creator_user = WalletUser.objects.create(address="0xcreator00000000000000000000000000000000")
        self.member_user = WalletUser.objects.create(address="0xmember00000000000000000000000000000000")
        self.non_member_user = WalletUser.objects.create(address="0xnonmember00000000000000000000000000000")

        from .models import Channel, ChannelMembership
        self.channel_all = Channel.objects.create(
            name="All Can Post",
            creator=self.creator_user,
            privacy_type=Channel.PrivacyType.PUBLIC,
            post_permission=Channel.PostPermission.ALL
        )
        self.channel_creator = Channel.objects.create(
            name="Creator Only Post",
            creator=self.creator_user,
            privacy_type=Channel.PrivacyType.PUBLIC,
            post_permission=Channel.PostPermission.CREATOR_ONLY
        )

        ChannelMembership.objects.create(channel=self.channel_all, user=self.member_user, status=ChannelMembership.Status.APPROVED)
        ChannelMembership.objects.create(channel=self.channel_creator, user=self.member_user, status=ChannelMembership.Status.APPROVED)

    def _auth(self, user):
        refresh = RefreshToken()
        refresh["address"] = user.address
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

    def test_member_can_post_in_all_channel(self):
        self._auth(self.member_user)
        url = reverse('post-list-create')
        response = self.client.post(url, {"content": "Hello", "channel_id": self.channel_all.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_member_cannot_post_in_creator_only_channel(self):
        self._auth(self.member_user)
        url = reverse('post-list-create')
        response = self.client.post(url, {"content": "Hello", "channel_id": self.channel_creator.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_creator_can_always_post(self):
        self._auth(self.creator_user)
        url = reverse('post-list-create')
        response = self.client.post(url, {"content": "Hello", "channel_id": self.channel_creator.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

class ChannelBanTestCase(APITestCase):
    def setUp(self):
        self.creator_user = WalletUser.objects.create(address="0xcreator00000000000000000000000000000000")
        self.member_user = WalletUser.objects.create(address="0xmember00000000000000000000000000000000")
        self.other_user = WalletUser.objects.create(address="0xother000000000000000000000000000000000")

        from .models import Channel, ChannelMembership
        self.channel = Channel.objects.create(
            name="Ban Test",
            creator=self.creator_user,
            privacy_type=Channel.PrivacyType.PUBLIC
        )
        ChannelMembership.objects.create(channel=self.channel, user=self.member_user, status=ChannelMembership.Status.APPROVED)

    def _auth(self, user):
        refresh = RefreshToken()
        refresh["address"] = user.address
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

    def test_creator_can_ban(self):
        self._auth(self.creator_user)
        url = reverse('channel-ban', kwargs={"pk": self.channel.id, "user_address": self.member_user.address})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "banned")

    def test_creator_cannot_ban_self(self):
        self._auth(self.creator_user)
        url = reverse('channel-ban', kwargs={"pk": self.channel.id, "user_address": self.creator_user.address})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_member_cannot_ban(self):
        self._auth(self.member_user)
        url = reverse('channel-ban', kwargs={"pk": self.channel.id, "user_address": self.other_user.address})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_banned_user_cannot_join(self):
        self._auth(self.creator_user)
        url = reverse('channel-ban', kwargs={"pk": self.channel.id, "user_address": self.other_user.address})
        self.client.post(url, format="json")

        self._auth(self.other_user)
        join_url = reverse('channel-join', kwargs={"pk": self.channel.id})
        response = self.client.post(join_url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_banned_user_cannot_post(self):
        self._auth(self.creator_user)
        url = reverse('channel-ban', kwargs={"pk": self.channel.id, "user_address": self.member_user.address})
        self.client.post(url, format="json")

        self._auth(self.member_user)
        post_url = reverse('post-list-create')
        response = self.client.post(post_url, {"content": "Hello", "channel_id": self.channel.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

class ChannelMemberListTestCase(APITestCase):
    def setUp(self):
        self.creator_user = WalletUser.objects.create(address="0xcreator00000000000000000000000000000000")
        self.member_user = WalletUser.objects.create(address="0xmember00000000000000000000000000000000")
        self.other_user = WalletUser.objects.create(address="0xother000000000000000000000000000000000")

        from .models import Channel, ChannelMembership
        self.public_channel = Channel.objects.create(
            name="Public Channel",
            creator=self.creator_user,
            privacy_type=Channel.PrivacyType.PUBLIC
        )
        self.private_channel = Channel.objects.create(
            name="Private Channel",
            creator=self.creator_user,
            privacy_type=Channel.PrivacyType.PRIVATE
        )
        ChannelMembership.objects.create(channel=self.public_channel, user=self.member_user, status=ChannelMembership.Status.APPROVED)
        ChannelMembership.objects.create(channel=self.private_channel, user=self.member_user, status=ChannelMembership.Status.APPROVED)

    def _auth(self, user):
        refresh = RefreshToken()
        refresh["address"] = user.address
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

    def test_public_member_list(self):
        url = reverse('channel-members', kwargs={"pk": self.public_channel.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["user_address"], self.member_user.address)

    def test_private_member_list_unauthenticated(self):
        url = reverse('channel-members', kwargs={"pk": self.private_channel.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_private_member_list_non_member(self):
        self._auth(self.other_user)
        url = reverse('channel-members', kwargs={"pk": self.private_channel.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_private_member_list_member(self):
        self._auth(self.member_user)
        url = reverse('channel-members', kwargs={"pk": self.private_channel.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_private_member_list_creator(self):
        self._auth(self.creator_user)
        url = reverse('channel-members', kwargs={"pk": self.private_channel.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

from unittest.mock import patch
from django.utils import timezone
from datetime import timedelta

class PositionTestCase(APITestCase):
    def setUp(self):
        self.creator_user = WalletUser.objects.create(address="0xcreator00000000000000000000000000000000")
        self.member_user = WalletUser.objects.create(address="0xmember00000000000000000000000000000000")
        self.other_user = WalletUser.objects.create(address="0xother000000000000000000000000000000000")

        from .models import Channel, ChannelMembership, Asset, Position
        self.channel = Channel.objects.create(
            name="Test Channel",
            creator=self.creator_user,
            privacy_type=Channel.PrivacyType.PUBLIC
        )
        ChannelMembership.objects.create(channel=self.channel, user=self.member_user, status=ChannelMembership.Status.APPROVED)
        
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider="binance",
            binance_symbol="BTCUSDT"
        )

    def _auth(self, user):
        refresh = RefreshToken()
        refresh["address"] = user.address
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

    @patch('posts.views.verify_position_signature')
    def test_create_valid_long_position(self, mock_verify):
        self._auth(self.creator_user)
        now = timezone.now()
        data = {
            "channel_id": self.channel.id,
            "asset_id": self.asset.id,
            "direction": "long",
            "entry_price": 50000,
            "entry_interval": (now + timedelta(days=1)).isoformat(),
            "stop_loss": 40000,
            "take_profit": 60000,
            "lifetime": (now + timedelta(days=7)).isoformat(),
            "signature": "0x123",
            "position_payload": {"fake": "payload"},
        }
        url = reverse('position-list-create')
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")

    @patch('posts.views.verify_position_signature')
    def test_create_invalid_long_position_sl_tp(self, mock_verify):
        self._auth(self.creator_user)
        now = timezone.now()
        data = {
            "channel_id": self.channel.id,
            "asset_id": self.asset.id,
            "direction": "long",
            "entry_price": 50000,
            "entry_interval": (now + timedelta(days=1)).isoformat(),
            "stop_loss": 60000,  # SL > entry
            "take_profit": 40000, # TP < entry
            "lifetime": (now + timedelta(days=7)).isoformat(),
            "signature": "0x123",
            "position_payload": {"fake": "payload"},
        }
        url = reverse('position-list-create')
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('posts.views.verify_position_signature')
    def test_create_invalid_short_position_sl_tp(self, mock_verify):
        self._auth(self.creator_user)
        now = timezone.now()
        data = {
            "channel_id": self.channel.id,
            "asset_id": self.asset.id,
            "direction": "short",
            "entry_price": 50000,
            "entry_interval": (now + timedelta(days=1)).isoformat(),
            "stop_loss": 40000,  # SL < entry
            "take_profit": 60000, # TP > entry
            "lifetime": (now + timedelta(days=7)).isoformat(),
            "signature": "0x123",
            "position_payload": {"fake": "payload"},
        }
        url = reverse('position-list-create')
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('posts.views.verify_position_signature')
    def test_create_invalid_dates(self, mock_verify):
        self._auth(self.creator_user)
        now = timezone.now()
        data = {
            "channel_id": self.channel.id,
            "asset_id": self.asset.id,
            "direction": "long",
            "entry_price": 50000,
            "entry_interval": (now - timedelta(days=1)).isoformat(), # Past
            "stop_loss": 40000,
            "take_profit": 60000,
            "lifetime": (now + timedelta(days=7)).isoformat(),
            "signature": "0x123",
            "position_payload": {"fake": "payload"},
        }
        url = reverse('position-list-create')
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("entry_interval", response.data)

        data["entry_interval"] = (now + timedelta(days=7)).isoformat()
        data["lifetime"] = (now + timedelta(days=1)).isoformat() # Before entry
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lifetime", response.data)

    @patch('posts.views.fetch_current_price')
    def test_close_position(self, mock_fetch):
        mock_fetch.return_value = (55000, "http://mock")
        
        self._auth(self.member_user)
        now = timezone.now()
        from .models import Position
        pos = Position.objects.create(
            author=self.member_user,
            channel=self.channel,
            asset=self.asset,
            direction="long",
            entry_price=50000,
            entry_interval=now + timedelta(days=1),
            stop_loss=40000,
            take_profit=60000,
            lifetime=now + timedelta(days=7),
            status=Position.Status.ACTIVE
        )

        url = reverse('position-close', kwargs={"pk": pos.id})
        response = self.client.post(url, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "closed_early")
        self.assertEqual(response.data["exit_price"], 55000)
        self.assertEqual(response.data["pnl_percentage"], 10.0)

    def test_close_inactive_position(self):
        self._auth(self.member_user)
        now = timezone.now()
        from .models import Position
        pos = Position.objects.create(
            author=self.member_user,
            channel=self.channel,
            asset=self.asset,
            direction="long",
            entry_price=50000,
            entry_interval=now + timedelta(days=1),
            stop_loss=40000,
            take_profit=60000,
            lifetime=now + timedelta(days=7),
            status=Position.Status.CONFIRMED # Not active
        )

        url = reverse('position-close', kwargs={"pk": pos.id})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_close_other_user_position(self):
        self._auth(self.other_user)
        now = timezone.now()
        from .models import Position
        pos = Position.objects.create(
            author=self.member_user,
            channel=self.channel,
            asset=self.asset,
            direction="long",
            entry_price=50000,
            entry_interval=now + timedelta(days=1),
            stop_loss=40000,
            take_profit=60000,
            lifetime=now + timedelta(days=7),
            status=Position.Status.ACTIVE
        )

        url = reverse('position-close', kwargs={"pk": pos.id})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PostFeedPaginationTestCase(APITestCase):
    def setUp(self):
        self.author = WalletUser.objects.create(address="0xauthor000000000000000000000000000000")
        for i in range(25):
            Post.objects.create(author=self.author, content=f"Post {i}")

    def test_feed_returns_paginated_response(self):
        url = reverse("post-list-create")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["page_size"], 20)
        self.assertTrue(response.data["has_next"])
        self.assertEqual(len(response.data["results"]), 20)

    def test_feed_page_two(self):
        url = reverse("post-list-create")
        response = self.client.get(url, {"page": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertFalse(response.data["has_next"])


class PostDetailTestCase(APITestCase):
    def setUp(self):
        self.author = WalletUser.objects.create(address="0xauthor000000000000000000000000000000")
        self.post = Post.objects.create(author=self.author, content="Detail me")

    def test_get_post_by_id(self):
        url = reverse("post-detail", kwargs={"pk": self.post.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.post.id)
        self.assertEqual(response.data["content"], "Detail me")

    def test_get_post_not_found(self):
        url = reverse("post-detail", kwargs={"pk": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ChannelRolesTestCase(APITestCase):
    def setUp(self):
        self.owner_user = WalletUser.objects.create(address="0xowner00000000000000000000000000000000")
        self.moderator_user = WalletUser.objects.create(address="0xmod0000000000000000000000000000000000")
        self.member_user = WalletUser.objects.create(address="0xmember00000000000000000000000000000000")
        self.other_member_user = WalletUser.objects.create(address="0xothermember0000000000000000000000000")
        
        self.asset = Asset.objects.create(
            name="Bitcoin",
            symbol="BTC",
            description="Digital gold",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.COINGECKO,
            provider_symbol="bitcoin",
        )

        from .models import Channel, ChannelMembership
        self.channel = Channel.objects.create(
            name="Role Test Channel",
            creator=self.owner_user,
            privacy_type=Channel.PrivacyType.PUBLIC
        )
        
        self.owner_membership = ChannelMembership.objects.create(
            channel=self.channel,
            user=self.owner_user,
            status=ChannelMembership.Status.APPROVED,
            role=ChannelMembership.Role.OWNER
        )
        
        self.mod_membership = ChannelMembership.objects.create(
            channel=self.channel,
            user=self.moderator_user,
            status=ChannelMembership.Status.APPROVED,
            role=ChannelMembership.Role.MODERATOR
        )
        
        self.member_membership = ChannelMembership.objects.create(
            channel=self.channel,
            user=self.member_user,
            status=ChannelMembership.Status.APPROVED,
            role=ChannelMembership.Role.MEMBER
        )

    def _auth(self, user):
        refresh = RefreshToken()
        refresh["address"] = user.address
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

    def test_one_channel_per_user(self):
        """Creating a second channel by the same user returns 400."""
        self._auth(self.owner_user)
        url = reverse("channel-list")
        data = {
            "name": "Second Channel",
            "description": "Fail please"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("You can only create one channel.", response.data["detail"])

    def test_moderator_can_ban(self):
        """A moderator can ban a regular member."""
        self._auth(self.moderator_user)
        url = reverse("channel-ban", kwargs={"pk": self.channel.id, "user_address": self.member_user.address})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.status, ChannelMembership.Status.BANNED)

    def test_moderator_cannot_ban_owner(self):
        """A moderator cannot ban the owner."""
        self._auth(self.moderator_user)
        url = reverse("channel-ban", kwargs={"pk": self.channel.id, "user_address": self.owner_user.address})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.status, ChannelMembership.Status.APPROVED)

    def test_owner_can_promote_moderator(self):
        """Owner can promote a member to moderator."""
        self._auth(self.owner_user)
        url = reverse("channel-moderator", kwargs={"pk": self.channel.id, "user_address": self.member_user.address})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, ChannelMembership.Role.MODERATOR)

        # Also test demote
        response_demote = self.client.delete(url, format="json")
        self.assertEqual(response_demote.status_code, status.HTTP_200_OK)
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, ChannelMembership.Role.MEMBER)

    def test_non_owner_cannot_promote(self):
        """A moderator cannot promote another moderator."""
        self._auth(self.moderator_user)
        url = reverse("channel-moderator", kwargs={"pk": self.channel.id, "user_address": self.member_user.address})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_author_cannot_delete_own_post(self):
        """Post author cannot delete their own post unless moderator/owner."""
        post = Post.objects.create(author=self.member_user, channel=self.channel, content="my post")
        self._auth(self.member_user)
        url = reverse("post-delete", kwargs={"pk": post.id})
        response = self.client.delete(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Post.objects.filter(id=post.id).exists())

    def test_moderator_can_delete_post(self):
        """A moderator can delete a channel post."""
        post = Post.objects.create(author=self.member_user, channel=self.channel, content="member post")
        self._auth(self.moderator_user)
        url = reverse("post-delete", kwargs={"pk": post.id})
        response = self.client.delete(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Post.objects.filter(id=post.id).exists())

    def test_member_cannot_delete_post(self):
        """A regular member cannot delete another member's post."""
        post = Post.objects.create(author=self.member_user, channel=self.channel, content="member post")
        self._auth(self.other_member_user)
        url = reverse("post-delete", kwargs={"pk": post.id})
        response = self.client.delete(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Post.objects.filter(id=post.id).exists())

    @patch('posts.views.verify_position_signature')
    def test_only_owner_can_create_position(self, mock_verify):
        """A regular member/moderator gets 403 when trying to create a position."""
        now = timezone.now()
        # Test moderator
        self._auth(self.moderator_user)
        data = {
            "channel_id": self.channel.id,
            "asset_id": self.asset.id,
            "direction": "long",
            "entry_price": 50000.0,
            "entry_interval": (now + timedelta(days=1)).isoformat(),
            "stop_loss": 40000.0,
            "take_profit": 60000.0,
            "lifetime": (now + timedelta(days=7)).isoformat(),
            "signature": "0x123",
            "position_payload": {"mock": "payload"},
        }
        url = reverse("position-list-create")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test owner
        self._auth(self.owner_user)
        response_owner = self.client.post(url, data, format="json")
        self.assertEqual(response_owner.status_code, status.HTTP_201_CREATED)

    def test_role_field_in_member_list(self):
        """Member list response includes the `role` field."""
        self._auth(self.member_user)
        url = reverse("channel-members", kwargs={"pk": self.channel.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify role is in serialization
        roles = {item["user_address"]: item["role"] for item in response.data}
        self.assertEqual(roles[self.owner_user.address], "owner")
        self.assertEqual(roles[self.moderator_user.address], "moderator")
        self.assertEqual(roles[self.member_user.address], "member")
