from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base

# teams | slack | webhook
CHANNEL_TYPES = ("teams", "slack", "webhook", "email")
SEVERITIES = ("info", "warning", "critical")
SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}
# Event types the platform can raise (a subset is wired to real triggers today).
ALERT_EVENTS = (
    "JOB_FAILED", "PIPELINE_FAILED", "SCHEDULE_OVERDUE", "CONNECTION_FAILED",
    "CLUSTER_UNAVAILABLE", "WORKER_DOWN", "JOB_ZERO_RECORDS", "SCHEMA_CHANGED", "RUNTIME_INVALID",
    "INTEGRATION_FAILED",
)


class AlertChannel(Base):
    """A notification destination (Teams/Slack/webhook). The URL is stored encrypted."""

    __tablename__ = "alert_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_url_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # Subscribed events (list of event types). NULL/empty => all events.
    events: Mapped[list | None] = mapped_column(JSONB)
    min_severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning", server_default="warning")
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class AlertNotification(Base):
    """One notification sent (or attempted) to a channel for an event."""

    __tablename__ = "alert_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int | None] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning", server_default="warning")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[int | None] = mapped_column(Integer)
    pipeline_id: Mapped[int | None] = mapped_column(Integer)
    execution_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    http_status: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
