"""Short-lived, stateless phone-verification token.

After a phone passes SMS OTP, we hand the client a signed token proving "this phone
was verified, recently". The client then includes it in the register call. We use a
signed JWT (via PyJWT, already a dependency of djangorestframework-simplejwt) rather
than server-side cache so it survives multi-worker gunicorn deployments — unlike the
login nonce, which relies on a shared/single-process cache.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings

from core.exceptions import ApiError

_PURPOSE = "phone_verify"
_TTL = timedelta(minutes=10)


def issue_phone_token(phone: str) -> str:
    """Return a signed token asserting ``phone`` was just verified."""
    now = datetime.now(timezone.utc)
    payload = {
        "phone": phone,
        "purpose": _PURPOSE,
        "iat": now,
        "exp": now + _TTL,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def read_phone_token(token: str) -> str:
    """Return the verified phone from ``token``, or raise ``ApiError`` if invalid/expired."""
    if not token:
        raise ApiError("Phone verification is required.", code="phone_unverified", status_code=400)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(
            "Phone verification expired. Please verify your number again.",
            code="phone_token_expired", status_code=400,
        ) from exc
    except jwt.PyJWTError as exc:
        raise ApiError(
            "Invalid phone verification. Please verify your number again.",
            code="phone_token_invalid", status_code=400,
        ) from exc
    if payload.get("purpose") != _PURPOSE or not payload.get("phone"):
        raise ApiError(
            "Invalid phone verification. Please verify your number again.",
            code="phone_token_invalid", status_code=400,
        )
    return payload["phone"]
