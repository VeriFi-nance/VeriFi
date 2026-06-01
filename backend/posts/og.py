from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import HardClaim, Position


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

class PositionOGView(APIView):
    """Lightweight public endpoint returning metadata for Open Graph tag generation for Positions."""
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        pos = get_object_or_404(
            Position.objects.select_related("asset", "author"),
            pk=pk,
        )

        direction = pos.direction.upper()
        symbol = pos.asset.symbol

        author_username = getattr(pos.author, "username", "") or ""
        author_display = f"@{author_username}" if author_username else pos.author.address[:10] + "…"

        title = f"✅ Verified Position: {direction} {symbol} — VeriFi"
        description = (
            f"Cryptographically signed position by {author_display}. "
            f"Entry: ${pos.entry_price}, TP: ${pos.take_profit}, SL: ${pos.stop_loss}."
        )

        return Response({
            "title": title,
            "description": description,
            "asset_symbol": symbol,
            "direction": direction,
            "entry_price": float(pos.entry_price),
            "take_profit": float(pos.take_profit) if pos.take_profit else None,
            "stop_loss": float(pos.stop_loss) if pos.stop_loss else None,
            "status": pos.status,
            "author_username": author_username,
        })

