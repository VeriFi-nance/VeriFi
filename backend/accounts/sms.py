"""Twilio Verify wrapper for SMS one-time-password (OTP) verification.

We use Twilio Verify (not raw Programmable SMS): Twilio generates, stores, expires,
and rate-limits the code. We only call ``start`` (send) and ``check`` (verify) — no
OTP is persisted on our side.

Local development: set ``TWILIO_DISABLED=true`` to skip Twilio entirely. In that mode
``start_verification`` is a no-op and ``check_verification`` accepts the fixed code
``000000`` (see ``DEV_BYPASS_CODE``), so the registration wizard is testable without
Twilio credentials or spending verification credits.
"""
from __future__ import annotations

import logging
import re

from django.conf import settings

from core.exceptions import ApiError

logger = logging.getLogger(__name__)

DEV_BYPASS_CODE = "000000"

# Twilio error codes worth surfacing with a clearer, user-facing message.
# https://www.twilio.com/docs/api/errors
_TWILIO_MESSAGES = {
    21211: "That phone number isn't valid.",
    21408: "We can't send SMS to that country yet.",
    21608: "This number isn't authorized on our SMS trial yet. "
           "Add it to Twilio Verified Caller IDs, or try a different number.",
    21610: "This number has opted out of messages.",
    60200: "That phone number isn't valid.",
    60203: "Too many attempts for this number. Wait a few minutes and try again.",
}


def _twilio_error(exc: Exception, *, default: str, code: str) -> ApiError:
    """Map a Twilio exception to an ApiError, surfacing known codes cleanly."""
    twilio_code = getattr(exc, "code", None)
    logger.warning("Twilio error (code=%s): %s", twilio_code, exc)
    message = _TWILIO_MESSAGES.get(twilio_code, default)
    fields = {"phone": [message]} if twilio_code in _TWILIO_MESSAGES else None
    return ApiError(message, code=code, status_code=502, fields=fields)

# E.164: leading '+', country digit 1-9, then up to 14 more digits.
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def normalize_phone(raw: str) -> str:
    """Validate and normalize a phone number to E.164, or raise ``ApiError``.

    Strips spaces, dashes, parens. Does not guess a country code — callers must
    send an international number (``+<country><number>``).
    """
    if not raw:
        raise ApiError("Phone number is required.", code="validation_error",
                       fields={"phone": ["Phone number is required."]})
    cleaned = re.sub(r"[\s\-()]", "", raw.strip())
    if not _E164_RE.match(cleaned):
        raise ApiError(
            "Enter a valid phone number in international format, e.g. +905321234567.",
            code="validation_error",
            fields={"phone": ["Enter a valid international phone number (e.g. +905321234567)."]},
        )
    return cleaned


def _twilio_disabled() -> bool:
    return getattr(settings, "TWILIO_DISABLED", False)


def _client():
    from twilio.rest import Client  # imported lazily so the dep isn't required in dev bypass

    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def start_verification(phone: str) -> None:
    """Send an OTP SMS to ``phone`` (already normalized). No-op in dev bypass mode."""
    if _twilio_disabled():
        return
    try:
        _client().verify.v2.services(
            settings.TWILIO_VERIFY_SERVICE_SID
        ).verifications.create(to=phone, channel="sms")
    except Exception as exc:  # network/Twilio failure — surface a clean error
        raise _twilio_error(
            exc,
            default="Could not send the verification code. Try again shortly.",
            code="sms_send_failed",
        ) from exc


def check_verification(phone: str, code: str) -> bool:
    """Return True if ``code`` is the valid OTP for ``phone``."""
    if not code:
        return False
    if _twilio_disabled():
        return code == DEV_BYPASS_CODE
    try:
        result = _client().verify.v2.services(
            settings.TWILIO_VERIFY_SERVICE_SID
        ).verification_checks.create(to=phone, code=code)
    except Exception as exc:
        raise _twilio_error(
            exc,
            default="Could not verify the code. Try again shortly.",
            code="sms_check_failed",
        ) from exc
    return getattr(result, "status", None) == "approved"
