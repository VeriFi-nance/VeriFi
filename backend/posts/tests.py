from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import WalletUser
from .models import Post, Asset, HardClaim
from .resolution import ResolutionError, fetch_due_price, fetch_reference_price, normalize_claim_for_resolution


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

    def test_create_hard_claim_success(self):
        """Test successfully creating a hard claim."""
        url = reverse('hard-claims')
        data = {
            'asset_id': self.asset.id,
            'direction': 'bullish',
            'percentage': 25.0,
            'until': '2027-12-31',
            'status': 'undetermined'
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

    def test_normalize_claim_for_resolution_rejects_missing_provider_symbol(self):
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
            normalize_claim_for_resolution(hard_claim)

        self.assertEqual(ctx.exception.code, "ASSET_PROVIDER_SYMBOL_MISSING")


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
            "prices": {"reference": 70000.0, "due": 78100.0, "currency": "USD"},
            "computed_change_pct": 11.57,
            "evaluation_reason": "due_price met or exceeded bullish percentage target",
            "resolved_at": "2026-05-01T09:00:00Z",
        }

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")
        mock_resolve.assert_called_once()

    @patch("posts.resolution._fetch_coingecko_price")
    def test_actual_resolution_persists_status_and_returns_computed_payload(self, mock_fetch):
        claim = self._make_claim(asset=self.crypto_asset, direction="bullish", percentage=10.0)
        mock_fetch.side_effect = [70000.0, 78100.0]

        with self.settings(ADMIN_ADDRESSES=[self.admin_address]):
            self._auth(self.admin_user)
            response = self.client.post(self._url(claim), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")
        self.assertEqual(response.data["prices"]["reference"], 70000.0)
        self.assertEqual(response.data["prices"]["due"], 78100.0)
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
            "prices": {"reference": 70000.0, "due": 60000.0, "currency": "USD"},
            "computed_change_pct": -14.29,
            "evaluation_reason": "due_price met or exceeded bearish percentage target",
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
            "prices": {"reference": 70000.0, "due": 74000.0, "currency": "USD"},
            "computed_change_pct": 5.71,
            "evaluation_reason": "due_price did not reach bullish percentage target",
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
        self.assertEqual(response.data["error_code"], "UNSUPPORTED_PROVIDER")

    @patch("posts.resolution._fetch_coingecko_price")
    def test_coingecko_provider_is_used_for_crypto(self, mock_fetch):
        claim = self._make_claim(asset=self.crypto_asset)
        mock_fetch.return_value = 70000.0

        payload = normalize_claim_for_resolution(claim)
        reference_price = fetch_reference_price(payload)
        due_price = fetch_due_price(payload)

        self.assertEqual(reference_price, 70000.0)
        self.assertEqual(due_price, 70000.0)
        self.assertEqual(mock_fetch.call_count, 2)

    @patch("posts.resolution._fetch_yfinance_price")
    def test_yfinance_provider_is_used_for_non_crypto(self, mock_fetch):
        claim = self._make_claim(asset=self.forex_asset)
        mock_fetch.return_value = 1.12

        payload = normalize_claim_for_resolution(claim)
        reference_price = fetch_reference_price(payload)
        due_price = fetch_due_price(payload)

        self.assertEqual(reference_price, 1.12)
        self.assertEqual(due_price, 1.12)
        self.assertEqual(mock_fetch.call_count, 2)

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
