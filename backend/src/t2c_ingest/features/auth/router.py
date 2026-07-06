from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from t2c_ingest.core.config import settings
from t2c_ingest.features.auth_bridge.deps import CurrentUser, get_current_user
from t2c_ingest.schemas.auth import LoginRequest, MeOut, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginRequest) -> TokenOut:
    """Login proxy: forwards credentials to the t2c_data backend, which owns the users and
    issues the JWT. The ingest product never stores passwords.

    The t2c_data /auth/login expects a JSON body {email, password, mfa_code?} and returns
    {access_token, ...}. Requires ``T2C_DATA_AUTH_BASE_URL`` to be configured."""
    base_url = (settings.t2c_data_auth_base_url or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login proxy não configurado. Defina T2C_DATA_AUTH_BASE_URL, ou faça login no t2c_data e reutilize o token.",
        )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base_url}/api/v1/auth/login",
                json=payload.model_dump(exclude_none=True),
            )
    except httpx.HTTPError as exc:  # pragma: no cover - network failure
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não foi possível contatar o serviço de autenticação do t2c_data em {base_url}.",
        ) from exc

    if resp.status_code != 200:
        # Surface the upstream detail (invalid credentials, MFA required, account locked...)
        detail = "Credenciais inválidas"
        try:
            body = resp.json()
            if isinstance(body, dict) and body.get("detail"):
                detail = body["detail"]
        except Exception:  # noqa: BLE001
            pass
        upstream = resp.status_code
        code = upstream if upstream in (401, 403, 422, 423) else status.HTTP_401_UNAUTHORIZED
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
