from django.contrib import admin
from .models import Post, Asset, HardClaim, OHLCData



@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["id", "author", "short_content", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["content", "author__address"]

    def short_content(self, obj):
        return obj.content[:80] + ("…" if len(obj.content) > 80 else "")
    short_content.short_description = "Content"


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "symbol", "market_type", "provider", "provider_symbol", "quote_currency"]
    list_filter = ["market_type", "provider", "quote_currency"]
    search_fields = ["name", "symbol", "provider_symbol"]
    fieldsets = (
        (None, {"fields": ("name", "symbol", "description", "market_type", "provider", "provider_symbol", "quote_currency")}),
        ("Exchange Symbols", {"fields": ("binance_symbol", "kucoin_symbol", "kraken_pair", "twelvedata_symbol")}),
    )


@admin.register(HardClaim)
class HardClaimAdmin(admin.ModelAdmin):
    list_display = ["id", "author", "asset", "direction", "percentage", "until", "status"]
    list_filter = ["status", "direction", "asset"]
    search_fields = ["text", "author__address"]


@admin.register(OHLCData)
class OHLCDataAdmin(admin.ModelAdmin):
    list_display = ["id", "asset", "timestamp", "interval", "open", "high", "low", "close"]
    list_filter = ["asset", "interval", "timestamp"]
    search_fields = ["asset__symbol"]
    ordering = ["-timestamp"]
