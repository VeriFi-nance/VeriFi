"""Normalized API error envelope.

Every error response the API emits should look like::

    {"error": {"code": "string_code", "message": "Human readable.", "fields": {...}}}

- ``code``    machine-stable identifier (e.g. ``insufficient_rep``, ``validation_error``).
- ``message`` always present, safe to surface directly in a toast.
- ``fields``  optional; per-field validation messages so forms can map errors to inputs.

`custom_exception_handler` wraps DRF's default handler so any *raised* exception
(serializer ``ValidationError``, auth/permission/404, or our own ``ApiError``)
is normalized. Views that still return ``Response({"detail": ...})`` manually
emit the legacy shape; the frontend client parses both during the migration.
"""
from __future__ import annotations

from typing import Any

from rest_framework import status as drf_status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(APIException):
    """Raise this for business-logic errors that should carry a stable code.

    Example::

        raise ApiError("Insufficient rep for listing fee + stake.",
                       code="insufficient_rep", status_code=400)
    """

    status_code = drf_status.HTTP_400_BAD_REQUEST
    default_detail = "Request failed."
    default_code = "error"

    def __init__(self, message: str | None = None, *, code: str | None = None,
                 status_code: int | None = None, fields: dict | None = None):
        if status_code is not None:
            self.status_code = status_code
        self.code = code or self.default_code
        self.fields = fields
        super().__init__(detail=message or self.default_detail)


def _first_message(data: Any) -> str:
    """Pull a human-readable string out of an arbitrary DRF error payload."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        if "detail" in data:
            return _first_message(data["detail"])
        for value in data.values():
            return _first_message(value)
    if isinstance(data, (list, tuple)) and data:
        return _first_message(data[0])
    return "Request failed."


def _field_errors(data: Any) -> dict | None:
    """Extract per-field validation messages, if the payload is field-shaped."""
    if not isinstance(data, dict):
        return None
    fields: dict[str, list[str]] = {}
    for key, value in data.items():
        if key == "detail":
            continue
        if isinstance(value, list):
            fields[key] = [str(v) for v in value]
        else:
            fields[key] = [str(value)]
    return fields or None


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        # Unhandled (500) — let Django's default machinery handle it.
        return None

    code = getattr(exc, "code", None) or getattr(exc, "default_code", None) or "error"
    fields = getattr(exc, "fields", None) or _field_errors(response.data)
    message = _first_message(response.data)

    envelope: dict[str, Any] = {"code": code, "message": message}
    if fields:
        envelope["fields"] = fields
    response.data = {"error": envelope}
    return response
