from django.db import models
from django.utils import timezone

from accounts.models import WalletUser


class Notification(models.Model):
    class Type(models.TextChoices):
        POST_LIKED = "post_liked", "Post liked"
        POST_SAVED = "post_saved", "Post proof saved"
        POST_COMMENTED = "post_commented", "Post commented"
        COMMENT_REPLIED = "comment_replied", "Comment replied"
        COMMENT_LIKED = "comment_liked", "Comment liked"
        FOLLOWED = "followed", "Followed"
        CHANNEL_JOIN_REQUEST = "channel_join_request", "Channel join request"
        CHANNEL_APPROVED = "channel_approved", "Channel approved"
        CHANNEL_REJECTED = "channel_rejected", "Channel rejected"
        CHANNEL_BANNED = "channel_banned", "Channel banned"
        CHANNEL_UNBANNED = "channel_unbanned", "Channel unbanned"
        CHANNEL_MODERATOR_ADDED = "channel_moderator_added", "Channel moderator added"
        CHANNEL_MODERATOR_REMOVED = "channel_moderator_removed", "Channel moderator removed"
        CLAIM_RESOLVED = "claim_resolved", "Claim resolved"
        CLAIM_MARKET_OPENED = "claim_market_opened", "Claim market opened"
        REP_SPENT = "rep_spent", "Rep spent"
        REP_PAYOUT = "rep_payout", "Rep payout"
        ENERGY_GRANTED = "energy_granted", "Energy granted"
        ENERGY_SPENT = "energy_spent", "Energy spent"
        POSITION_ENTRY_TRIGGERED = "position_entry_triggered", "Position entry triggered"
        POSITION_RESOLVED = "position_resolved", "Position resolved"

    recipient = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(
        WalletUser,
        on_delete=models.SET_NULL,
        related_name="notifications_sent",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=40, choices=Type.choices)
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=280, blank=True, default="")
    target_url = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(blank=True, default=dict)
    dedupe_key = models.CharField(max_length=160, unique=True, null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at", "-created_at"], name="notif_recipient_read_idx"),
            models.Index(fields=["recipient", "-created_at"], name="notif_recipient_created_idx"),
            models.Index(fields=["dedupe_key"], name="notif_dedupe_idx"),
        ]

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    def __str__(self):
        return f"Notification<{self.type} to={self.recipient_id}>"
