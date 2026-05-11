from django.db import models


class WalletUser(models.Model):
    address = models.CharField(max_length=42, unique=True)  # Ethereum address: 0x + 40 hex
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.address


class Follow(models.Model):
    follower = models.ForeignKey(WalletUser, related_name="following_set", on_delete=models.CASCADE)
    following = models.ForeignKey(WalletUser, related_name="follower_set", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("follower", "following")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(follower=models.F('following')),
                name="no_self_follow"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.follower.address[:10]} follows {self.following.address[:10]}"
