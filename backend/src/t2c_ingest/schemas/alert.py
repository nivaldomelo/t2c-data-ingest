from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    channel_type: str = "webhook"  # teams | slack | webhook
    target_url: str
    active: bool = True
    events: list[str] = Field(default_factory=list)
    min_severity: str = "warning"


class ChannelUpdate(BaseModel):
    name: str | None = None
    channel_type: str | None = None
    target_url: str | None = None
    active: bool | None = None
    events: list[str] | None = None
    min_severity: str | None = None


class ChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    channel_type: str
    active: bool
    events: list[str] | None = None
    min_severity: str
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    # Masked target (never returns the raw webhook URL/secret).
    target_masked: str | None = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int | None = None
    channel_name: str | None = None
    event_type: str
    severity: str
    title: str
    message: str | None = None
    job_id: int | None = None
    pipeline_id: int | None = None
    execution_id: int | None = None
    status: str
    http_status: int | None = None
    error: str | None = None
    attempts: int = 0
    created_at: datetime
    sent_at: datetime | None = None


class TestChannelResult(BaseModel):
    status: str
    http_status: int | None = None
    error: str | None = None
