from django.contrib import admin
from .models import Post, Claim, Asset, HardClaim


class ClaimInline(admin.TabularInline):
    model = Claim
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["id", "author", "short_content", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["content", "author__address"]
    inlines = [ClaimInline]

    def short_content(self, obj):
        return obj.content[:80] + ("…" if len(obj.content) > 80 else "")
    short_content.short_description = "Content"


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ["id", "post", "text", "asset", "direction", "status"]
    list_filter = ["status", "asset"]
    search_fields = ["text"]


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "symbol", "market_type", "provider", "provider_symbol", "quote_currency"]
    list_filter = ["market_type", "provider", "quote_currency"]
    search_fields = ["name", "symbol", "provider_symbol"]


@admin.register(HardClaim)
class HardClaimAdmin(admin.ModelAdmin):
    list_display = ["id", "author", "asset", "direction", "percentage", "until", "status"]
    list_filter = ["status", "direction", "asset"]
    search_fields = ["text", "author__address"]
