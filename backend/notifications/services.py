from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from accounts.models import WalletUser

from .models import Notification

logger = logging.getLogger(__name__)


def notify(
    *,
    recipient: WalletUser | None,
    type: str,
    title: str,
    message: str = "",
    actor: WalletUser | None = None,
    target_url: str = "",
    metadata: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    suppress_self: bool = True,
) -> Notification | None:
    if recipient is None:
        return None
    if suppress_self and actor is not None and actor.pk == recipient.pk:
        return None

    payload = {
        "recipient": recipient,
        "actor": actor,
        "type": type,
        "title": title[:120],
        "message": message[:280],
        "target_url": target_url[:255],
        "metadata": metadata or {},
    }
    if dedupe_key:
        payload["dedupe_key"] = dedupe_key[:160]

    try:
        if dedupe_key:
            notification, _ = Notification.objects.get_or_create(
                dedupe_key=payload["dedupe_key"],
                defaults=payload,
            )
            return notification
        return Notification.objects.create(**payload)
    except Exception:
        logger.exception("Failed to create notification %s for user %s", type, recipient.pk)
        return None


def notify_once(**kwargs) -> Notification | None:
    if not kwargs.get("dedupe_key"):
        raise ValueError("notify_once requires dedupe_key")
    return notify(**kwargs)


def mark_read(notification: Notification) -> Notification:
    notification.mark_read()
    return notification


def mark_all_read(recipient: WalletUser) -> int:
    updated = Notification.objects.filter(recipient=recipient, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return updated
