from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.core.db import get_db
from t2c_ingest.core.security import create_access_token, verify_password
from t2c_ingest.features.auth_bridge.deps import CurrentUser, get_current_user
from t2c_ingest.features.auth_bridge.models import ReferenceUser
from t2c_ingest.schemas.auth import LoginRequest, MeOut, TokenOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    """Authenticate a user.

    - ``AUTH_MODE=direct`` (default): verify the password against t2c_data.users in the shared
      Postgres and mint the JWT here — no dependency on the t2c_data backend being up. Reuses
      the same credentials; it does not create or store any new user.
    - ``AUTH_MODE=proxy``: forward credentials to the t2c_data backend, which issues the token.
    """
    if settings.auth_mode.strip().lower() == "proxy":
        return await _login_via_proxy(payload)
    return _login_direct(payload, db)


def _login_direct(payload: LoginRequest, db: Session) -> TokenOut:
    user = db.scalar(select(ReferenceUser).where(ReferenceUser.email == payload.email.strip()))
    # Constant-ish path: same error whether the user is missing or the password is wrong.
    if not user or not verify_password(payload.password, user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo"
        )
    # DEV SIMPLIFICATION: MFA is not enforced in direct mode. Users with MFA enabled in
    # t2c_data still log in here without a code. Use AUTH_MODE=proxy for full MFA handling.
    if user.mfa_enabled:
        logger.warning("Usuário %s tem MFA habilitado; ignorado no login direto (dev).", user.email)
    token = create_access_token(user.email, token_version=int(user.token_version or 0))
    return TokenOut(access_token=token)


async def _login_via_proxy(payload: LoginRequest) -> TokenOut:
    base_url = (settings.t2c_data_auth_base_url or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_MODE=proxy requer T2C_DATA_AUTH_BASE_URL configurado.",
        )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base_url}/api/v1/auth/login", json=payload.model_dump(exclude_none=True)
            )
    except httpx.HTTPError as exc:  # pragma: no cover - network failure
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não foi possível contatar o serviço de autenticação do t2c_data em {base_url}.",
        ) from exc

    if resp.status_code != 200:
        detail = "Credenciais inválidas"
        try:
            body = resp.json()
            if isinstance(body, dict) and body.get("detail"):
                detail = body["detail"]
        except Exception:  # noqa: BLE001
            pass
        code = resp.status_code if resp.status_code in (401, 403, 422, 423) else status.HTTP_401_UNAUTHORIZED
        raise HTTPException(status_code=code, detail=detail)

    token = resp.json().get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resposta inesperada do serviço de autenticação do t2c_data (sem access_token).",
        )
    return TokenOut(access_token=token)


@router.get("/me", response_model=MeOut)
def me(current_user: CurrentUser = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        roles=sorted(current_user.roles),
        permissions=sorted(current_user.permissions),
    )
