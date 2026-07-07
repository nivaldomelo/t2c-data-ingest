from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from t2c_ingest.core.config import settings

# Same scheme configuration as t2c_data so its stored hashes (argon2, bcrypt) verify here.
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:  # noqa: BLE001 - malformed/unknown hash
        return False


def create_access_token(subject: str, *, token_version: int = 0, expires_minutes: int | None = None) -> str:
    """Mint a JWT with the shared secret (mirrors t2c_data's token: sub, tv, iat, exp)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "tv": int(token_version),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


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
