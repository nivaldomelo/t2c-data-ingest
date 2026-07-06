from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from t2c_ingest.core.config import settings
from t2c_ingest.features.auth_bridge.deps import CurrentUser, get_current_user
from t2c_ingest.schemas.auth import MeOut, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenOut:
    """Login proxy: forwards credentials to the t2c_data backend, which owns the users and
    issues the JWT. The ingest product never stores passwords. Requires
    ``T2C_DATA_AUTH_BASE_URL`` to be configured."""
    base_url = (settings.t2c_data_auth_base_url or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login proxy not configured. Set T2C_DATA_AUTH_BASE_URL, or log in via t2c_data and reuse the token.",
        )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base_url}/api/v1/auth/login",
                data={"username": form.username, "password": form.password},
            )
    except httpx.HTTPError as exc:  # pragma: no cover - network failure
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach t2c_data authentication service.",
        ) from exc

    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected response from t2c_data authentication service.",
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
