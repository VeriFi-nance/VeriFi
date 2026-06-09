from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.energy import DAILY_GRANT, grant_energy
from accounts.models import Follow, WalletUser
from notifications.models import Notification
from posts.models import (
    Asset,
    Channel,
    ChannelMembership,
    ClaimMarket,
    HardClaim,
    Position,
    Post,
    PostComment,
)


def token(user):
    refresh = RefreshToken()
    refresh["address"] = user.address
    return str(refresh.access_token)


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.user = WalletUser.objects.create(address="0x" + "1" * 40, username="one")
        self.other = WalletUser.objects.create(address="0x" + "2" * 40, username="two")

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token(user)}")

    def test_notification_api_requires_auth_and_scopes_to_recipient(self):
        Notification.objects.create(
            recipient=self.user,
            type=Notification.Type.FOLLOWED,
            title="Hello",
        )
        Notification.objects.create(
            recipient=self.other,
            type=Notification.Type.FOLLOWED,
            title="Hidden",
        )

        self.assertEqual(self.client.get(reverse("notification-list")).status_code, 401)

        self.auth(self.user)
        response = self.client.get(reverse("notification-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Hello")

    def test_mark_read_and_mark_all_read(self):
        first = Notification.objects.create(
            recipient=self.user,
            type=Notification.Type.FOLLOWED,
            title="First",
        )
        Notification.objects.create(
            recipient=self.user,
            type=Notification.Type.FOLLOWED,
            title="Second",
        )
        self.auth(self.user)

        count = self.client.get(reverse("notification-unread-count"))
        self.assertEqual(count.data["unread_count"], 2)

        read = self.client.patch(reverse("notification-read", kwargs={"pk": first.pk}))
        self.assertEqual(read.status_code, 200)
        self.assertFalse(read.data["unread"])

        all_read = self.client.post(reverse("notification-mark-all-read"))
        self.assertEqual(all_read.status_code, 200)
        self.assertEqual(Notification.objects.filter(recipient=self.user, read_at__isnull=True).count(), 0)

    def test_delete_scopes_to_recipient(self):
        mine = Notification.objects.create(
            recipient=self.user,
            type=Notification.Type.FOLLOWED,
            title="Mine",
        )
        theirs = Notification.objects.create(
            recipient=self.other,
            type=Notification.Type.FOLLOWED,
            title="Theirs",
        )

        self.assertEqual(self.client.delete(reverse("notification-delete", kwargs={"pk": mine.pk})).status_code, 401)

        self.auth(self.user)
        # Cannot delete another user's notification.
        self.assertEqual(
            self.client.delete(reverse("notification-delete", kwargs={"pk": theirs.pk})).status_code, 404
        )
        self.assertTrue(Notification.objects.filter(pk=theirs.pk).exists())

        deleted = self.client.delete(reverse("notification-delete", kwargs={"pk": mine.pk}))
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Notification.objects.filter(pk=mine.pk).exists())


class NotificationEmitterTests(APITestCase):
    def setUp(self):
        self.author = WalletUser.objects.create(address="0x" + "a" * 40, username="author")
        self.viewer = WalletUser.objects.create(address="0x" + "b" * 40, username="viewer")
        self.other = WalletUser.objects.create(address="0x" + "c" * 40, username="other")
        self.asset = Asset.objects.create(name="Bitcoin", symbol="BTC", provider_symbol="bitcoin")
        self.post = Post.objects.create(author=self.author, content="Social proof")

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token(user)}")

    def test_social_notifications_are_deduped_and_suppress_self(self):
        self.auth(self.viewer)
        like_url = reverse("post-like", kwargs={"pk": self.post.pk})
        self.client.post(like_url)
        self.client.post(like_url)

        self.assertEqual(
            Notification.objects.filter(recipient=self.author, type=Notification.Type.POST_LIKED).count(),
            1,
        )

        self.auth(self.author)
        own_post = Post.objects.create(author=self.author, content="My post")
        self.client.post(reverse("post-like", kwargs={"pk": own_post.pk}))
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.author,
                type=Notification.Type.POST_LIKED,
                metadata__post_id=own_post.pk,
            ).exists()
        )

    def test_comment_reply_and_comment_like_notifications(self):
        parent = PostComment.objects.create(post=self.post, author=self.other, content="Parent")
        self.auth(self.viewer)

        created = self.client.post(
            reverse("post-comments", kwargs={"pk": self.post.pk}),
            {"content": "Reply", "parent_id": parent.pk},
            format="json",
        )
        self.assertEqual(created.status_code, 201)

        self.assertTrue(
            Notification.objects.filter(recipient=self.other, type=Notification.Type.COMMENT_REPLIED).exists()
        )
        self.assertTrue(
            Notification.objects.filter(recipient=self.author, type=Notification.Type.POST_COMMENTED).exists()
        )

        self.client.post(reverse("post-comment-like", kwargs={"pk": parent.pk}))
        self.client.post(reverse("post-comment-like", kwargs={"pk": parent.pk}))
        self.assertEqual(
            Notification.objects.filter(recipient=self.other, type=Notification.Type.COMMENT_LIKED).count(),
            1,
        )

    def test_follow_and_channel_notifications(self):
        self.auth(self.viewer)

        follow_response = self.client.post("/api/auth/follow/", {"target_address": self.author.address}, format="json")
        self.assertEqual(follow_response.status_code, 200)
        self.assertEqual(Follow.objects.count(), 1)
        self.assertTrue(Notification.objects.filter(recipient=self.author, type=Notification.Type.FOLLOWED).exists())

        channel = Channel.objects.create(name="Signals", creator=self.author)
        ChannelMembership.objects.create(
            channel=channel,
            user=self.author,
            status=ChannelMembership.Status.APPROVED,
            role=ChannelMembership.Role.OWNER,
        )
        join_response = self.client.post(reverse("channel-join", kwargs={"pk": channel.pk}))
        self.assertEqual(join_response.status_code, 201)
        self.assertTrue(
            Notification.objects.filter(recipient=self.author, type=Notification.Type.CHANNEL_JOIN_REQUEST).exists()
        )

        self.auth(self.author)
        approve = self.client.post(
            reverse("channel-approve", kwargs={"pk": channel.pk, "user_address": self.viewer.address}),
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(approve.status_code, 200)
        self.assertTrue(
            Notification.objects.filter(recipient=self.viewer, type=Notification.Type.CHANNEL_APPROVED).exists()
        )

    def test_manual_claim_resolution_notifies_once(self):
        admin = WalletUser.objects.create(address="0x" + "d" * 40, username="admin")
        claim = HardClaim.objects.create(
            author=self.author,
            asset=self.asset,
            direction="bullish",
            percentage=10,
            until="2027-12-31",
        )
        self.auth(admin)

        with self.settings(ADMIN_ADDRESSES=[admin.address]):
            url = reverse("hard-claim-update-status", kwargs={"pk": claim.pk})
            self.client.patch(url, {"status": HardClaim.Status.CONFIRMED}, format="json")
            self.client.patch(url, {"status": HardClaim.Status.CONFIRMED}, format="json")

        self.assertEqual(
            Notification.objects.filter(recipient=self.author, type=Notification.Type.CLAIM_RESOLVED).count(),
            1,
        )

    @patch("posts.views.verify_claim_signature")
    def test_market_energy_and_rep_spend_notifications(self, _mock_verify):
        self.author.energy = 3
        self.author.rep = 100
        self.author.last_energy_grant = timezone.now()
        self.author.save(update_fields=["energy", "rep", "last_energy_grant"])
        self.auth(self.author)

        response = self.client.post(
            reverse("hard-claims"),
            {
                "asset_id": self.asset.id,
                "direction": "bullish",
                "percentage": 10,
                "until": "2027-12-31",
                "signature": "0x123",
                "claim_payload": {"asset_symbol": "BTC", "author_username": self.author.username},
                "market": {"side": "YES", "stake_rep": 10},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Notification.objects.filter(recipient=self.author, type=Notification.Type.ENERGY_SPENT).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.author, type=Notification.Type.REP_SPENT).exists())
        self.assertTrue(
            Notification.objects.filter(recipient=self.author, type=Notification.Type.CLAIM_MARKET_OPENED).exists()
        )

    def test_market_buy_and_refund_notifications(self):
        self.author.rep = 100
        self.viewer.rep = 100
        self.author.save(update_fields=["rep"])
        self.viewer.save(update_fields=["rep"])
        claim = HardClaim.objects.create(
            author=self.author,
            asset=self.asset,
            direction="bullish",
            percentage=10,
            until="2027-12-31",
            status=HardClaim.Status.CONFIRMED,
        )
        from posts import rep_market

        rep_market.init_market(claim, self.author, "YES", 10)
        market = ClaimMarket.objects.get(hard_claim=claim)
        self.auth(self.viewer)
        buy = self.client.post(reverse("hard-claim-market-buy", kwargs={"pk": claim.pk}), {"side": "NO"}, format="json")
        self.assertEqual(buy.status_code, 201)
        self.assertTrue(Notification.objects.filter(recipient=self.viewer, type=Notification.Type.REP_SPENT).exists())

        from posts.resolution import _maybe_settle_rep_market

        _maybe_settle_rep_market(claim)
        market.refresh_from_db()
        self.assertTrue(market.resolved)
        self.assertTrue(Notification.objects.filter(type=Notification.Type.REP_PAYOUT).exists())

    @patch("posts.position_resolution.get_ohlc_data", return_value=[])
    def test_position_resolution_notification_is_deduped(self, _mock_ohlc):
        from posts.position_resolution import _resolve_pending

        position = Position.objects.create(
            author=self.author,
            asset=self.asset,
            direction=Position.Direction.LONG,
            entry_price=100,
            entry_interval=timezone.now() - timedelta(hours=1),
            stop_loss=90,
            take_profit=120,
            lifetime=timezone.now() + timedelta(days=1),
        )

        _resolve_pending(position, timezone.now())
        _resolve_pending(position, timezone.now())

        self.assertEqual(
            Notification.objects.filter(recipient=self.author, type=Notification.Type.POSITION_RESOLVED).count(),
            1,
        )


class EnergyNotificationTests(TestCase):
    def test_grant_energy_notifies_only_when_energy_is_added(self):
        user = WalletUser.objects.create(
            address="0x" + "e" * 40,
            username="energy",
            energy=1,
            last_energy_grant=timezone.now() - timedelta(days=1),
        )

        grant_energy(user)
        grant_energy(user)

        self.assertEqual(user.notifications.filter(type=Notification.Type.ENERGY_GRANTED).count(), 1)
        self.assertEqual(user.notifications.first().metadata["amount"], DAILY_GRANT)
