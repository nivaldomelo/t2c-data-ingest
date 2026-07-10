from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base

# job | pipeline | control_group | control_table
BACKFILL_KINDS = ("job", "pipeline", "control_group", "control_table")
# queued | running | success | partial | failed
BACKFILL_STATUSES = ("queued", "running", "success", "partial", "failed")


class BackfillRun(Base):
    """A controlled reprocessing request: reprocess a job, a pipeline (optionally from a step),
    or a control group/table over an optional period, with optional watermark reset."""

    __tablename__ = "backfill_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    job_id: Mapped[int | None] = mapped_column(Integer)
    pipeline_id: Mapped[int | None] = mapped_column(Integer)
    from_step_id: Mapped[int | None] = mapped_column(Integer)
    pipeline_execution_id: Mapped[int | None] = mapped_column(Integer)
    control_group: Mapped[str | None] = mapped_column(String(100))
    table_name: Mapped[str | None] = mapped_column(Text)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    reset_watermark: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    watermark_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", server_default="queued")
    total_targets: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    execution_ids: Mapped[list | None] = mapped_column(JSONB)
    watermarks_reset: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
