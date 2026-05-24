"""
Asset Updater & Notification Engine — Observer Design Pattern.

This module implements the Subject (Observable) side of the pattern:
  1. update_asset_price()  — fetches fresh OHLC data from external APIs and persists it
  2. notify_subscribers()  — iterates the AssetSubscription table and dispatches
                             resolution logic to each subscribed Position
  3. update_all_assets()   — orchestrator that updates every asset and notifies subscribers

The periodic scheduler (cron / management command) calls update_all_assets().
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.utils import timezone

from .models import Asset, AssetSubscription, OHLCData, Position, PositionEvent
from .ohlc_fetcher import OHLCFetchError, fetch_ohlc_for_asset
from .position_resolution import _resolve_pending, _resolve_active

logger = logging.getLogger(__name__)


def update_asset_price(asset: Asset) -> list[OHLCData]:
    """
    Fetch fresh OHLC data from external APIs, save to DB, update timestamp.

    Uses the cascading fallback chain defined in ohlc_fetcher.py:
      - Crypto:       Binance → Kucoin → Kraken
      - Traditional:  Yahoo Finance → Twelve Data

    Raises OHLCFetchError if all providers fail for this asset.
    """
    today = date.today()

    # Determine the earliest date we need data for: look at the oldest
    # active subscription's position creation date, or default to 30 days ago
    subscriptions = AssetSubscription.objects.filter(asset=asset).select_related("position")
    if subscriptions.exists():
        earliest_position_date = min(
            sub.position.created_at.date() for sub in subscriptions
        )
        start_date = earliest_position_date
    else:
        # No active subscribers, but we still update the asset's price data
        start_date = today - timedelta(days=30)

    # 1. Fetch directly from external APIs (skip DB cache)
    raw_rows = fetch_ohlc_for_asset(asset, start_date, today)

    # 2. Persist the fetched data into OHLCData table
    new_ohlc = [
        OHLCData(
            asset=asset,
            timestamp=row["timestamp"],
            interval="1d",
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
        )
        for row in raw_rows
    ]
    if new_ohlc:
        OHLCData.objects.bulk_create(new_ohlc, ignore_conflicts=True)

    # 3. Update the asset's last_price_update timestamp
    asset.last_price_update = timezone.now()
    asset.save(update_fields=["last_price_update"])

    # 4. Return the saved OHLCData model instances for notification
    return list(
        OHLCData.objects.filter(
            asset=asset, timestamp__date__gte=start_date, timestamp__date__lte=today, interval="1d"
        ).order_by("timestamp")
    )


def notify_subscribers(asset: Asset, ohlc_data: list[OHLCData]) -> dict:
    """
    Iterate the asset's subscriber list (AssetSubscription) and notify
    each subscribed Position by running its resolution logic.

    Returns a summary dict with counts of transitions and errors.
    """
    # Explicitly query the AssetSubscription model (the subscriber list)
    subscriptions = AssetSubscription.objects.filter(
        asset=asset
    ).select_related("position")

    summary = {"notified": 0, "transitioned": 0, "errors": 0}

    for sub in subscriptions:
        try:
            changed = _notify_position(sub.position, ohlc_data, sub)
            summary["notified"] += 1
            if changed:
                summary["transitioned"] += 1
        except Exception as e:
            logger.error(
                "Error notifying position %d for asset %s: %s",
                sub.position.id, asset.symbol, e
            )
            summary["errors"] += 1

    return summary


def _notify_position(
    position: Position,
    ohlc_data: list[OHLCData],
    subscription: AssetSubscription,
) -> bool:
    """
    Observer update() — runs resolution logic for a single position.

    Returns True if the position's status changed (state transition occurred).
    """
    now = timezone.now()
    old_status = position.status

    if position.status == Position.Status.PENDING:
        _resolve_pending(position, now)
    elif position.status == Position.Status.ACTIVE:
        _resolve_active(position, now)
    else:
        # Position is already in a terminal state — should not be subscribed
        # Clean up the stale subscription
        subscription.delete()
        return False

    # Refresh to check if status changed
    position.refresh_from_db()

    # If position reached a terminal state → unsubscribe
    terminal_statuses = {
        Position.Status.MISSED,
        Position.Status.CONFIRMED,
        Position.Status.REJECTED,
        Position.Status.EXPIRED,
        Position.Status.CLOSED_EARLY,
    }
    if position.status in terminal_statuses:
        subscription.delete()  # unsubscribe()

    return position.status != old_status


def update_all_assets() -> dict:
    """
    Main orchestrator: update every asset's price data, then notify subscribers.

    This is the entry point called by the management command / scheduler.
    Returns a summary dict with per-asset results.
    """
    results = {
        "assets_updated": 0,
        "assets_failed": 0,
        "total_notified": 0,
        "total_transitioned": 0,
        "total_errors": 0,
    }

    for asset in Asset.objects.all():
        try:
            ohlc_data = update_asset_price(asset)
            results["assets_updated"] += 1

            summary = notify_subscribers(asset, ohlc_data)
            results["total_notified"] += summary["notified"]
            results["total_transitioned"] += summary["transitioned"]
            results["total_errors"] += summary["errors"]

        except OHLCFetchError as e:
            # All API providers failed for this asset — log and skip
            logger.error("All sources failed for %s: %s", asset.symbol, e)
            # last_price_update stays unchanged (stale)
            results["assets_failed"] += 1
            continue
        except Exception as e:
            logger.error("Unexpected error for %s: %s", asset.symbol, e)
            results["assets_failed"] += 1
            continue

    return results
