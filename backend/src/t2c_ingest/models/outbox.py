from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base


class IntegrationOutbox(Base):
    """Reliable outbox for pushes to t2c_data (lineage, data quality, schema, S3, incidents...).

    A producer enqueues a row in its own transaction; the worker's publisher delivers it with
    retry + exponential backoff and marks it sent/dead. An idempotency_key deduplicates events so
    a retried delivery never double-writes in t2c_data.

    status: pending | processing | sent | failed | dead
    """

    __tablename__ = "integration_outbox"
    __table_args__ = (
        Index("ix_ingest_outbox_status", "status", "id"),
        Index("ix_ingest_outbox_next_attempt", "next_attempt_at"),
        Index("ix_ingest_outbox_event_type", "event_type"),
        Index("ix_ingest_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_type: Mapped[str | None] = mapped_column(String(100))
    aggregate_id: Mapped[str | None] = mapped_column(String(150))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    # `error` is the legacy column; `error_message` mirrors the recommended model name.
    error: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
