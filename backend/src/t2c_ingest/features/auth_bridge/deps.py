from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.security import decode_token_payload
from t2c_ingest.features.auth_bridge.models import ReferenceUser
from t2c_ingest.features.auth_bridge.permissions import (
    ADMIN_ROLE_NAMES,
    permissions_for_roles,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass
class CurrentUser:
    id: int
    email: str
    name: str | None
    roles: set[str] = field(default_factory=set)
    permissions: set[str] = field(default_factory=set)

    @property
    def is_admin(self) -> bool:
        return bool(self.roles & ADMIN_ROLE_NAMES)

    def has(self, permission: str) -> bool:
        return self.is_admin or permission in self.permissions


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    payload = decode_token_payload(token)
    email = payload.get("sub") if payload else None
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user = db.scalar(select(ReferenceUser).where(ReferenceUser.email == email))
    except SQLAlchemyError as exc:  # pragma: no cover - infra failure
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de autenticação indisponível: falha ao consultar o banco do t2c_data.",
        ) from exc

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing"
        )

    token_version = payload.get("tv") if payload else None
    if int(token_version or 0) != int(getattr(user, "token_version", 0) or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired or invalid"
        )

    role_names = {r.name for r in user.roles}
    return CurrentUser(
        id=user.id,
        email=user.email,
        name=user.name or user.full_name,
        roles=role_names,
        permissions=permissions_for_roles(role_names),
    )


def require_permission(permission_name: str):
    """Dependency factory enforcing an ingest permission (admins always pass)."""

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current_user.has(permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permission: {permission_name}",
            )
        return current_user

    return _dependency
