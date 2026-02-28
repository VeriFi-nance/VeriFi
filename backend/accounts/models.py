from django.db import models


class WalletUser(models.Model):
    public_key = models.CharField(max_length=66, unique=True)  # hex compressed secp256k1
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.public_key[:16] + "..."
