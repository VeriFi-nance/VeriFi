from django.contrib import admin
from .models import WalletUser


@admin.register(WalletUser)
class WalletUserAdmin(admin.ModelAdmin):
    list_display = ("id", "address", "created_at")
    search_fields = ("address",)
    readonly_fields = ("address", "created_at")
    ordering = ("-created_at",)
