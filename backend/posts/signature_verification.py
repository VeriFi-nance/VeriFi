"""
Signature verification for HardClaim and Position payloads.

Server-side enforcement: every new claim/position must carry a valid
EIP-191 secp256k1 signature. Three checks are performed:

1. **Signer recovery** — the recovered Ethereum address must match
   the authenticated user's wallet address.
2. **Payload consistency** — the signed canonical JSON must match
   the actual request data.
3. **Timestamp freshness** — ``created_at`` inside the payload must
   be within ±5 minutes of server time (anti-replay).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

from eth_account.messages import encode_defunct
from eth_account import Account
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

TIMESTAMP_TOLERANCE = timedelta(minutes=5)


def _recover_address(message: str, signature_hex: str) -> str:
    """Recover Ethereum address from an EIP-191 personal_sign signature."""
    sig = signature_hex if signature_hex.startswith("0x") else f"0x{signature_hex}"
    msg = encode_defunct(text=message)
    return Account.recover_message(msg, signature=sig).lower()


def _canonical_json(payload: dict) -> str:
    """Deterministic JSON: sorted keys, no whitespace, no trailing newline."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _parse_timestamp(ts_str: str) -> datetime:
    """Parse an ISO-8601 timestamp. Accepts both with and without 'Z'."""
    s = ts_str.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _check_timestamp_freshness(payload: dict) -> None:
    """Raise if created_at is too far from server time."""
    ts_str = payload.get("created_at")
    if not ts_str:
        raise ValidationError({"signature": "Payload missing 'created_at' timestamp."})
    try:
        ts = _parse_timestamp(ts_str)
    except (ValueError, TypeError):
        raise ValidationError({"signature": "Invalid 'created_at' timestamp format."})

    now = datetime.now(timezone.utc)
    if abs(now - ts) > TIMESTAMP_TOLERANCE:
        raise ValidationError(
            {"signature": "Payload timestamp is stale or too far in the future (±5 min)."}
        )


# -------------------------------------------------------------------------
# HardClaim verification
# -------------------------------------------------------------------------

def _build_expected_claim_payload(request_data: dict, asset_symbol: str) -> dict:
    """Build what we *expect* the signed payload to contain, from request data."""
    return {
        "asset_symbol": asset_symbol,
        "created_at": request_data.get("created_at", ""),
        "direction": request_data.get("direction", ""),
        "percentage": float(request_data.get("percentage", 0)),
        "until": request_data.get("until", ""),
    }


def verify_claim_signature(
    user_address: str,
    signature: str,
    claim_payload: dict,
    asset_symbol: str,
) -> None:
    """
    Validate a HardClaim signature.  Raises ``ValidationError`` on failure.

    Parameters
    ----------
    user_address : str
        The authenticated user's Ethereum address (lowercase).
    signature : str
        Hex-encoded EIP-191 signature from the client.
    claim_payload : dict
        The canonical JSON payload that the client claims to have signed.
    asset_symbol : str
        The asset symbol resolved from asset_id — used to verify payload
        consistency.
    """
    if not signature:
        raise ValidationError({"signature": "Signature is required."})
    if not claim_payload:
        raise ValidationError({"claim_payload": "Claim payload is required."})

    # 1. Timestamp freshness
    _check_timestamp_freshness(claim_payload)

    # 2. Payload consistency — the payload fields must match request data
    expected = _build_expected_claim_payload(claim_payload, asset_symbol)
    actual = {
        "asset_symbol": claim_payload.get("asset_symbol", ""),
        "created_at": claim_payload.get("created_at", ""),
        "direction": claim_payload.get("direction", ""),
        "percentage": float(claim_payload.get("percentage", 0)),
        "until": claim_payload.get("until", ""),
    }
    if expected != actual:
        raise ValidationError(
            {"signature": "Signed payload does not match request data."}
        )

    # 3. Signer recovery
    canonical = _canonical_json(claim_payload)
    try:
        recovered = _recover_address(canonical, signature)
    except Exception as exc:
        logger.warning("Signature recovery failed: %s", exc)
        raise ValidationError({"signature": "Invalid signature: recovery failed."})

    if recovered != user_address.lower():
        raise ValidationError(
            {"signature": "Signature does not match the authenticated wallet address."}
        )


# -------------------------------------------------------------------------
# Position verification
# -------------------------------------------------------------------------

def _build_expected_position_payload(request_data: dict, asset_symbol: str) -> dict:
    """Build what we *expect* the signed position payload to contain."""
    return {
        "asset_symbol": asset_symbol,
        "created_at": request_data.get("created_at", ""),
        "direction": request_data.get("direction", ""),
        "entry_price": float(request_data.get("entry_price", 0)),
        "lifetime": request_data.get("lifetime", ""),
        "stop_loss": float(request_data.get("stop_loss", 0)),
        "take_profit": float(request_data.get("take_profit", 0)),
    }


def verify_position_signature(
    user_address: str,
    signature: str,
    position_payload: dict,
    asset_symbol: str,
) -> None:
    """
    Validate a Position signature.  Raises ``ValidationError`` on failure.
    """
    if not signature:
        raise ValidationError({"signature": "Signature is required."})
    if not position_payload:
        raise ValidationError({"position_payload": "Position payload is required."})

    # 1. Timestamp freshness
    _check_timestamp_freshness(position_payload)

    # 2. Payload consistency
    expected = _build_expected_position_payload(position_payload, asset_symbol)
    actual = {
        "asset_symbol": position_payload.get("asset_symbol", ""),
        "created_at": position_payload.get("created_at", ""),
        "direction": position_payload.get("direction", ""),
        "entry_price": float(position_payload.get("entry_price", 0)),
        "lifetime": position_payload.get("lifetime", ""),
        "stop_loss": float(position_payload.get("stop_loss", 0)),
        "take_profit": float(position_payload.get("take_profit", 0)),
    }
    if expected != actual:
        raise ValidationError(
            {"signature": "Signed payload does not match request data."}
        )

    # 3. Signer recovery
    canonical = _canonical_json(position_payload)
    try:
        recovered = _recover_address(canonical, signature)
    except Exception as exc:
        logger.warning("Position signature recovery failed: %s", exc)
        raise ValidationError({"signature": "Invalid signature: recovery failed."})

    if recovered != user_address.lower():
        raise ValidationError(
            {"signature": "Signature does not match the authenticated wallet address."}
        )
