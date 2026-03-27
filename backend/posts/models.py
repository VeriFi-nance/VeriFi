from django.db import models
from accounts.models import WalletUser


class Post(models.Model):
    author = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="posts")
    content = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author.address[:10]}… — {self.content[:40]}"
    
class Claim(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed"
        REJECTED = "rejected"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="claims")
    text = models.TextField()
    asset = models.CharField(max_length=50, blank=True, default="")
    direction = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default="confirmed")

    def __str__(self):
        return f"{self.asset} {self.direction}: {self.text[:40]}"


class Asset(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
    
class HardClaim(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed"
        UNDETERMINED = "undetermined"
        REJECTED = "rejected"

    author = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="hard_claims", null=True, blank=True)
    text = models.TextField()
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, blank=False, null=False)
    direction = models.CharField(max_length=20, blank=True, default="") # this will be binary, 1 up, 0 down
    percentage = models.FloatField(blank=False, null=False) # this will be a percentage value between 0 and 100
    until = models.DateField(blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=Status.choices, default="undetermined")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(until__gt=models.F("created_at")),
                name="hardclaim_until_after_created_at",
            )
        ]

    def __str__(self):
        return f"{self.asset} {self.direction}: {self.text[:40]}"

