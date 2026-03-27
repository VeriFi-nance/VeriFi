from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import WalletUser
from .models import Post, Asset, HardClaim


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
            description="Digital gold"
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
            'text': 'Bitcoin will reach $100,000 by end of 2025',
            'asset_id': self.asset.id,
            'direction': 'bullish',
            'percentage': 25.0,
            'until': '2025-12-31',
            'status': 'undetermined'
        }

        response = self.client.post(url, data, format='json')

        # Assert response status
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Assert response data contains expected fields
        self.assertIn('id', response.data)
        self.assertIn('author_address', response.data)
        self.assertIn('text', response.data)
        self.assertIn('asset', response.data)
        self.assertIn('direction', response.data)
        self.assertIn('percentage', response.data)
        self.assertIn('until', response.data)
        self.assertIn('status', response.data)

        # Assert response values
        self.assertEqual(response.data['text'], 'Bitcoin will reach $100,000 by end of 2025')
        self.assertEqual(response.data['direction'], 'bullish')
        self.assertEqual(response.data['percentage'], 25.0)
        self.assertEqual(response.data['until'], '2025-12-31')
        self.assertEqual(response.data['status'], 'undetermined')
        self.assertEqual(response.data['author_address'], self.wallet_user.address)

        # Assert the hard claim was created in the database with correct author
        hard_claim = HardClaim.objects.get(id=response.data['id'])
        self.assertEqual(hard_claim.author, self.wallet_user)
        self.assertEqual(hard_claim.asset, self.asset)
        self.assertEqual(hard_claim.text, 'Bitcoin will reach $100,000 by end of 2025')
        self.assertEqual(hard_claim.direction, 'bullish')
        self.assertEqual(hard_claim.percentage, 25.0)
        self.assertEqual(str(hard_claim.until), '2025-12-31')
        self.assertEqual(hard_claim.status, 'undetermined')

    def test_create_hard_claim_invalid_data(self):
        """Test creating a hard claim with invalid data."""
        url = reverse('hard-claims')
        data = {
            'text': 'Invalid claim',
            'asset_id': 9999,  # Non-existent asset ID
            'percentage': 10.0,
            'until': '2025-12-31'
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
            'text': 'Bitcoin will reach $100,000 by end of 2025',
            'asset_id': self.asset.id,
            'direction': 'bullish',
            'percentage': 25.0,
            'until': '2025-12-31'
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

        self.asset = Asset.objects.create(name="Bitcoin", symbol="BTC", description="Digital gold")
        self.hard_claim = HardClaim.objects.create(
            author=self.regular_user,
            text="BTC to $100k",
            asset=self.asset,
            direction="bullish",
            percentage=20.0,
            until="2025-12-31",
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