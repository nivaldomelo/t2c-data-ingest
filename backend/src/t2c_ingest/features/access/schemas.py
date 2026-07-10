from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccessUserOut(BaseModel):
    """A t2c_data user annotated with their access status in the ingest tool."""

    email: str
    name: str | None = None
    roles: list[str] = []
    is_active: bool = True
    is_admin: bool = False
    has_access: bool = False


class GrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    note: str | None = None
    active: bool
    granted_by: str | None = None
    created_at: datetime


class GrantIn(BaseModel):
    email: str
    note: str | None = None


class AccessSummary(BaseModel):
    admins: int = 0
    granted: int = 0
    total_users: int = 0
