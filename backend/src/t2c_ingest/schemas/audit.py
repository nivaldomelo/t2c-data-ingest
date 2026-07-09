from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    user_email: str | None = None
    ip_address: str | None = None
    detail: Any = None
    created_at: datetime


class AuditActionCount(BaseModel):
    action: str
    count: int


class AuditSummary(BaseModel):
    total: int = 0
    today: int = 0
    last_7d: int = 0
    distinct_users_7d: int = 0
    top_actions: list[AuditActionCount] = Field(default_factory=list)
