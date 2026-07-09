from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    roles: list[str]
    permissions: list[str]
    is_admin: bool = False
    has_access: bool = False
