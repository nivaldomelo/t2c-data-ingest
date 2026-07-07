from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from t2c_ingest.models.base import Base
from t2c_ingest.models.common import TimestampMixin

# cron | hourly | daily | weekly | monthly | manual
SCHEDULE_TYPES = ("cron", "hourly", "daily", "weekly", "monthly", "manual")


class JobSchedule(TimestampMixin, Base):
    """An automatic-execution schedule for a job (Airflow-like)."""

    __tablename__ = "job_schedules"
    __table_args__ = (Index("ix_ingest_job_schedules_active_next", "active", "next_run_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    schedule_type: Mapped[str] = mapped_column(String(20), nullable=False, default="cron")
    cron_expression: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(60), nullable=False, default="America/Sao_Paulo")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_status: Mapped[str | None] = mapped_column(String(20))
    created_by: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(255))

    runs: Mapped[list["ScheduleRun"]] = relationship(
        "ScheduleRun", back_populates="schedule", cascade="all, delete-orphan"
    )


class ScheduleRun(Base):
    """One trigger attempt of a schedule, linked to the execution it created."""

    __tablename__ = "schedule_runs"
    __table_args__ = (
        # Idempotency: a schedule fires at most once for a given planned instant.
        UniqueConstraint("schedule_id", "scheduled_for", name="uq_ingest_schedule_runs_slot"),
        Index("ix_ingest_schedule_runs_schedule", "schedule_id", "triggered_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("job_schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"), index=True
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="triggered")
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    schedule: Mapped["JobSchedule"] = relationship("JobSchedule", back_populates="runs")
