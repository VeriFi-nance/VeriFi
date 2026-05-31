from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import WalletUser

class UsernameTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_generates_username(self):
        # When no username is provided, it should generate one from address
        address = "0x" + "a" * 40
        res = self.client.post("/api/auth/register/", {"address": address})
        self.assertEqual(res.status_code, 201)
        self.assertIn("username", res.data)
        user = WalletUser.objects.get(address=address)
        self.assertTrue(user.username.startswith("0xaaaa"))

    def test_register_with_username(self):
        # When a valid username is provided, it should be used
        address = "0x" + "b" * 40
        res = self.client.post("/api/auth/register/", {"address": address, "username": "custom_user"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["username"], "custom_user")
        user = WalletUser.objects.get(address=address)
        self.assertEqual(user.username, "custom_user")

    def test_register_duplicate_username(self):
        # When an existing username is provided, it should fail
        address1 = "0x" + "1" * 40
        WalletUser.objects.create(address=address1, username="taken_name")

        address2 = "0x" + "2" * 40
        res = self.client.post("/api/auth/register/", {"address": address2, "username": "taken_name"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("username", res.data)

    def test_profile_lookup_by_username_and_address(self):
        address = "0x" + "c" * 40
        WalletUser.objects.create(address=address, username="lookup_user")
        
        # By Address
        res_addr = self.client.get(f"/api/auth/profile/{address}/")
        self.assertEqual(res_addr.status_code, 200)
        self.assertEqual(res_addr.data["username"], "lookup_user")

        # By Username
        res_usr = self.client.get("/api/auth/profile/lookup_user/")
        self.assertEqual(res_usr.status_code, 200)
        self.assertEqual(res_usr.data["address"], address)

    def test_profile_update_username(self):
        address = "0x" + "d" * 40
        user = WalletUser.objects.create(address=address, username="old_name")
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken()
        token["address"] = address

        # Change username successfully
        res = self.client.patch("/api/auth/profile/update/", {"username": "new_name"}, format="json", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["username"], "new_name")
        user.refresh_from_db()
        self.assertEqual(user.username, "new_name")

    def test_profile_update_duplicate_username(self):
        # Create another user to take the name
        WalletUser.objects.create(address="0x123", username="taken")
        
        address = "0x" + "e" * 40
        user = WalletUser.objects.create(address=address, username="my_name")
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken()
        token["address"] = address

        # Attempt to change to taken username
        res = self.client.patch("/api/auth/profile/update/", {"username": "taken"}, format="json", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("detail", res.data)
        self.assertEqual(res.data["detail"], "Username is already taken.")
