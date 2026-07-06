from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base


class AuditEvent(Base):
    """Audit trail for ingest actions (create/run/cancel/migrate...)."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_ingest_audit_events_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
