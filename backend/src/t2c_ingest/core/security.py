from __future__ import annotations

import jwt

from t2c_ingest.core.config import settings


def decode_token_payload(token: str) -> dict | None:
    """Decode a JWT issued by t2c_data using the shared secret.

    The ingest product never issues its own credentials; it validates the same HS256 token
    t2c_data emits (payload: ``sub`` = email, ``tv`` = token_version, optional ``jti``).
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.InvalidTokenError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def decode_token(token: str) -> str | None:
    payload = decode_token_payload(token)
    if payload is None:
        return None
    return payload.get("sub")
