from django.db import models


class WalletUser(models.Model):
    address = models.CharField(max_length=42, unique=True)  # Ethereum address: 0x + 40 hex
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.address
