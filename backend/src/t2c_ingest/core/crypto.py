from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from t2c_ingest.core.config import settings


def _fernet() -> Fernet:
    """Build a Fernet cipher from the configured secret.

    The connection secret is derived into a valid 32-byte urlsafe key. Set
    CONNECTION_SECRET_KEY in production; in dev it falls back to the JWT secret so the app
    works out of the box (connection passwords are still encrypted at rest, never plaintext).
    """
    secret = (settings.connection_secret_key or settings.jwt_secret_key or "change-me").encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str | None) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        # Key rotated or corrupted blob — treat as no usable secret rather than crashing.
        return ""
