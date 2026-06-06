from cloudinary.models import CloudinaryField
from django.db import models


class WalletUser(models.Model):
    address = models.CharField(max_length=42, unique=True)  # Ethereum address: 0x + 40 hex
    username = models.CharField(max_length=30, unique=True)
    avatar = CloudinaryField("avatar", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rep = models.FloatField(default=200.0)
    energy = models.FloatField(default=4.0)
    last_energy_grant = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.username:
            base = self.address[:6]
            self.username = base
            counter = 1
            while WalletUser.objects.filter(username__iexact=self.username).exclude(pk=self.pk).exists():
                self.username = f"{base}_{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


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

class ProfitabilityCache(models.Model):
    user = models.OneToOneField(WalletUser, on_delete=models.CASCADE, related_name="profitability")
    pnl_7d = models.FloatField(default=0.0)
    pnl_30d = models.FloatField(default=0.0)
    pnl_all = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profitability({self.user.address[:10]}): {self.pnl_all}%"
