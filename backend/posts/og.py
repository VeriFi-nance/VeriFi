from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import HardClaim


class HardClaimOGView(APIView):
    """Lightweight public endpoint returning metadata for Open Graph tag generation."""
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        claim = get_object_or_404(
            HardClaim.objects.select_related("asset", "author"),
            pk=pk,
        )

        direction = claim.direction.lower()
        verb = "rises" if direction == "bullish" else "falls"
        pct = float(claim.percentage)
        until_str = claim.until.strftime("%b %d, %Y")
        symbol = claim.asset.symbol

        author_username = getattr(claim.author, "username", "") or ""
        author_display = f"@{author_username}" if author_username else claim.author.address[:10] + "…"

        title = f"✅ Verified: {symbol} {verb} {pct}% by {until_str} — VeriFi"
        description = (
            f"Cryptographically signed prediction by {author_display}. "
            f"Verify the proof yourself on VeriFi."
        )

        return Response({
            "title": title,
            "description": description,
            "asset_symbol": symbol,
            "direction": direction,
            "percentage": pct,
            "until": claim.until.isoformat(),
            "status": claim.status,
            "author_username": author_username,
        })
