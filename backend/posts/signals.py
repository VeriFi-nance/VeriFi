"""
Signal handlers for the posts app.

Track how often each Asset is referenced so the search/filter dropdowns can
surface the most-used assets first. An atomic F() update avoids read-modify-
write races when many claims/positions are created concurrently.
"""

from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Asset, HardClaim, Position


def _bump_asset_usage(asset_id: int | None) -> None:
    if asset_id is None:
        return
    Asset.objects.filter(pk=asset_id).update(usage_count=F("usage_count") + 1)


@receiver(post_save, sender=HardClaim)
def hardclaim_bumps_asset(sender, instance, created, **kwargs):
    if created:
        _bump_asset_usage(instance.asset_id)


@receiver(post_save, sender=Position)
def position_bumps_asset(sender, instance, created, **kwargs):
    if created:
        _bump_asset_usage(instance.asset_id)
