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
