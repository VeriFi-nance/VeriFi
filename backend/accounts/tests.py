from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from accounts.models import WalletUser, ProfileChangeLog

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
        self.assertIn("username", res.data["error"]["fields"])

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
        entry = ProfileChangeLog.objects.get(user=user)
        self.assertEqual(entry.event_type, ProfileChangeLog.EventType.USERNAME_UPDATED)
        self.assertEqual(entry.metadata["old_username"], "old_name")
        self.assertEqual(entry.metadata["new_username"], "new_name")

        profile = self.client.get(f"/api/auth/profile/{address}/")
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["changelog"][0]["event_type"], "username_updated")
        self.assertIn("@old_name", profile.data["changelog"][0]["summary"])

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
        self.assertIn("username", res.data["error"]["fields"])

    def test_register_username_starts_with_0x(self):
        # Trying to register with a username starting with '0x' should fail
        address = "0x" + "1a" * 20
        res = self.client.post("/api/auth/register/", {"address": address, "username": "0xmyuser"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("username", res.data["error"]["fields"])

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

    # Note: A `test_profile_lookup_shadowing` test was removed because shadowing is
    # structurally impossible. A username (max 30 chars) can never equal a
    # 42-char address, and the '0x' prefix guard further reinforces this.
    def test_profile_lookup_not_found(self):
        # Non-existent user returns 404
        res_none = self.client.get("/api/auth/profile/non_existent/")
        self.assertEqual(res_none.status_code, 404)

    def test_profile_channels(self):
        from posts.models import Channel, ChannelMembership
        address = "0x" + "f" * 40
        user = WalletUser.objects.create(address=address, username="channel_user")
        
        channel_owned = Channel.objects.create(name="Owned Comm", creator=user)
        ChannelMembership.objects.create(channel=channel_owned, user=user, status="approved", role="owner")

        other_user = WalletUser.objects.create(address="0x" + "e" * 40, username="other_user")
        channel_joined = Channel.objects.create(name="Joined Comm", creator=other_user)
        
        # User is not approved member yet
        ChannelMembership.objects.create(channel=channel_joined, user=user, status="pending")
        
        # Verify pending membership doesn't show up
        res = self.client.get(f"/api/auth/profile/{address}/")
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.data["channel_owned"])
        self.assertEqual(res.data["channel_owned"]["id"], channel_owned.id)
        self.assertEqual(len(res.data["channels_member_of"]), 0)
        
        # Make membership approved
        membership = ChannelMembership.objects.get(channel=channel_joined, user=user)
        membership.status = "approved"
        membership.save()
        
        # Verify approved membership shows up
        res = self.client.get(f"/api/auth/profile/{address}/")
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.data["channel_owned"])
        self.assertEqual(len(res.data["channels_member_of"]), 1)
        self.assertEqual(res.data["channels_member_of"][0]["id"], channel_joined.id)

    def test_follow_accepts_username_lookup(self):
        follower_address = "0x" + "a1" * 20
        target_address = "0x" + "b2" * 20
        WalletUser.objects.create(address=follower_address, username="follower_user")
        WalletUser.objects.create(address=target_address, username="target_user")
        token = AccessToken()
        token["address"] = follower_address

        res = self.client.post(
            "/api/auth/follow/",
            {"target_address": "target_user"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["following"])

    def test_follow_rejects_self_by_username(self):
        address = "0x" + "c3" * 20
        WalletUser.objects.create(address=address, username="self_user")
        token = AccessToken()
        token["address"] = address

        res = self.client.post(
            "/api/auth/follow/",
            {"target_address": "self_user"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["detail"], "Cannot follow yourself.")
