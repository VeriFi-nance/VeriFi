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
        WalletUser.objects.create(address=address, username="my_name")
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken()
        token["address"] = address

        # Attempt to change to taken username
        res = self.client.patch("/api/auth/profile/update/", {"username": "taken"}, format="json", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("detail", res.data)
        self.assertEqual(res.data["detail"], "Username is already taken.")

    def test_register_reserved_username(self):
        # Trying to register with a reserved name should fail
        address = "0x" + "f" * 40
        res = self.client.post("/api/auth/register/", {"address": address, "username": "update"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("username", res.data)

    def test_register_username_starts_with_0x(self):
        # Trying to register with a username starting with '0x' should fail
        address = "0x" + "1a" * 20
        res = self.client.post("/api/auth/register/", {"address": address, "username": "0xmyuser"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("username", res.data)

    def test_profile_update_reserved_username(self):
        address = "0x" + "2b" * 20
        WalletUser.objects.create(address=address, username="valid_name")
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken()
        token["address"] = address

        # Attempt to update to a reserved name
        res = self.client.patch("/api/auth/profile/update/", {"username": "follow"}, format="json", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("detail", res.data)
        self.assertEqual(res.data["detail"], "This username is reserved.")

    def test_profile_update_username_starts_with_0x(self):
        address = "0x" + "3c" * 20
        WalletUser.objects.create(address=address, username="valid_name2")
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken()
        token["address"] = address

        # Attempt to update to a username starting with 0x
        res = self.client.patch("/api/auth/profile/update/", {"username": "0xother"}, format="json", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("detail", res.data)
        self.assertEqual(res.data["detail"], "Username cannot start with '0x'.")

    def test_profile_lookup_shadowing(self):
        # User A's address is identical to User B's username
        address_a = "0x" + "a" * 40
        user_a = WalletUser.objects.create(address=address_a, username="user_a")
        
        address_b = "0x" + "b" * 40
        user_b = WalletUser.objects.create(address=address_b, username=address_a)

        # Lookup address_a (User A's address, which is also User B's username)
        res = self.client.get(f"/api/auth/profile/{address_a}/")
        self.assertEqual(res.status_code, 200)
        # Should return User A, prioritizing the address match
        self.assertEqual(res.data["address"], address_a)
        self.assertEqual(res.data["username"], "user_a")

        # Lookup address_b (User B's address)
        res_b = self.client.get(f"/api/auth/profile/{address_b}/")
        self.assertEqual(res_b.status_code, 200)
        self.assertEqual(res_b.data["address"], address_b)
        self.assertEqual(res_b.data["username"], address_a)

        # Non-existent user returns 404
        res_none = self.client.get("/api/auth/profile/non_existent/")
        self.assertEqual(res_none.status_code, 404)

