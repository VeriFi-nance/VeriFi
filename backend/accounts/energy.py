"""Lazy daily energy grant for Model G."""
from __future__ import annotations

from datetime import datetime, time, timezone as dt_tz

from django.db import transaction
from django.utils import timezone

DAILY_GRANT = 3
ENERGY_CAP = None
INITIAL_ENERGY = 4
CLAIM_ENERGY_COST = 1
STAKE_ENERGY_COST = 1


def _utc_midnight(dt: datetime) -> datetime:
    return datetime.combine(dt.astimezone(dt_tz.utc).date(), time.min, tzinfo=dt_tz.utc)


def grant_energy(user) -> None:
    """Idempotent lazy regrant. Adds DAILY_GRANT per whole UTC day elapsed."""
    now = timezone.now()
    last = user.last_energy_grant
    if last is None:
        user.energy = max(user.energy, float(INITIAL_ENERGY))
        user.last_energy_grant = now
        user.save(update_fields=["energy", "last_energy_grant"])
        return
    days = (_utc_midnight(now) - _utc_midnight(last)).days
    if days <= 0:
        return
    granted = days * DAILY_GRANT
    user.energy = user.energy + days * DAILY_GRANT
    user.last_energy_grant = now
    user.save(update_fields=["energy", "last_energy_grant"])
    try:
        from notifications.emitters import notify_energy_granted

        notify_energy_granted(
            user,
            float(granted),
            f"energy-grant:{user.pk}:{now.astimezone(dt_tz.utc).date().isoformat()}",
        )
    except Exception:
        pass


def spend(user, cost: int) -> bool:
    """Atomically decrement energy. Returns True on success, False if insufficient."""
    from .models import WalletUser

    with transaction.atomic():
        locked = WalletUser.objects.select_for_update().get(pk=user.pk)
        grant_energy(locked)
        if locked.energy < cost:
            return False
        locked.energy -= cost
        locked.save(update_fields=["energy"])
        user.energy = locked.energy
        user.last_energy_grant = locked.last_energy_grant
    return True
