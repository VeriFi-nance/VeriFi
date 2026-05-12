from django.utils import timezone
from datetime import timedelta
from posts.models import Position
from accounts.models import WalletUser, ProfitabilityCache

def recalculate_profitability(user: WalletUser):
    now = timezone.now()
    
    # Resolved statuses
    resolved_statuses = [
        Position.Status.CONFIRMED,
        Position.Status.REJECTED,
        Position.Status.EXPIRED,
        Position.Status.CLOSED_EARLY
    ]
    
    positions = Position.objects.filter(
        author=user,
        status__in=resolved_statuses,
        pnl_percentage__isnull=False
    )
    
    pnl_all = sum(pos.pnl_percentage for pos in positions)
    
    # 7-Day window
    date_7d = now - timedelta(days=7)
    pnl_7d = sum(pos.pnl_percentage for pos in positions if pos.created_at >= date_7d)
    
    # 30-Day window
    date_30d = now - timedelta(days=30)
    pnl_30d = sum(pos.pnl_percentage for pos in positions if pos.created_at >= date_30d)
    
    cache, _ = ProfitabilityCache.objects.update_or_create(
        user=user,
        defaults={
            "pnl_7d": pnl_7d,
            "pnl_30d": pnl_30d,
            "pnl_all": pnl_all
        }
    )
    return cache

def recalculate_all_profitabilities():
    resolved_statuses = [
        Position.Status.CONFIRMED,
        Position.Status.REJECTED,
        Position.Status.EXPIRED,
        Position.Status.CLOSED_EARLY
    ]
    
    users_with_positions = WalletUser.objects.filter(
        positions__status__in=resolved_statuses,
        positions__pnl_percentage__isnull=False
    ).distinct()
    
    for user in users_with_positions:
        recalculate_profitability(user)
