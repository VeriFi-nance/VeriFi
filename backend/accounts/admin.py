from django.contrib import admin
from .models import WalletUser


@admin.register(WalletUser)
class WalletUserAdmin(admin.ModelAdmin):
    list_display = ("id", "public_key", "created_at")
    search_fields = ("public_key",)
    readonly_fields = ("public_key", "created_at")
    ordering = ("-created_at",)
