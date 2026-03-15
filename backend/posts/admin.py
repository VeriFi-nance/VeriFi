from django.contrib import admin
from .models import Post, Claim


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
