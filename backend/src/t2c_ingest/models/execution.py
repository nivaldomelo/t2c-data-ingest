from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from t2c_ingest.models.base import Base
from t2c_ingest.models.common import TimestampMixin

# queued | running | success | failed | cancelled | skipped | timeout
EXECUTION_STATUSES = (
    "queued",
    "running",
    "success",
    "failed",
    "cancelled",
    "skipped",
    "timeout",
)


class Execution(TimestampMixin, Base):
    """One run of a job or a pipeline. The API only records queued status and enqueues;
    the worker/cluster performs the heavy work and updates status/logs."""

    __tablename__ = "executions"
    __table_args__ = (
        Index("ix_ingest_executions_status_started", "status", "started_at"),
        Index("ix_ingest_executions_triggered_by", "triggered_by"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # job | pipeline
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_definitions.id", ondelete="SET NULL"), index=True
    )
    pipeline_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_definitions.id", ondelete="SET NULL"), index=True
    )
    # denormalized for fast listing/filtering
    target_name: Mapped[str | None] = mapped_column(String(200))
    job_type: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    # manual | schedule | api | pipeline | retry
    trigger_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    schedule_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # python_worker | spark_cluster
    engine: Mapped[str | None] = mapped_column(String(20))
    cluster_id: Mapped[int | None] = mapped_column(
        ForeignKey("clusters.id", ondelete="SET NULL"), index=True
    )
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    triggered_by: Mapped[str | None] = mapped_column(String(255))
    # Retry attempt number (1-based). Reliability fields: lease/heartbeat for orphan recovery,
    # cancel_requested for cooperative cancellation of a running job.
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    worker_id: Mapped[str | None] = mapped_column(String(120))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    final_message: Mapped[str | None] = mapped_column(Text)
    error_trace: Mapped[str | None] = mapped_column(Text)
    # parent execution for per-step pipeline runs
    parent_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    step_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_steps.id", ondelete="SET NULL"), index=True
    )

    logs: Mapped[list["ExecutionLog"]] = relationship(
        "ExecutionLog", back_populates="execution", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["ExecutionArtifact"]] = relationship(
        "ExecutionArtifact", back_populates="execution", cascade="all, delete-orphan"
    )
    runtime_parameters: Mapped[list["RuntimeParameter"]] = relationship(
        "RuntimeParameter", back_populates="execution", cascade="all, delete-orphan"
    )


class ExecutionLog(TimestampMixin, Base):
    __tablename__ = "execution_logs"
    __table_args__ = (
        Index("ix_ingest_execution_logs_execution_seq", "execution_id", "seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_id: Mapped[int | None] = mapped_column(Integer, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # DEBUG | INFO | WARNING | ERROR
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    logged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    execution: Mapped["Execution"] = relationship("Execution", back_populates="logs")


class ExecutionArtifact(TimestampMixin, Base):
    __tablename__ = "execution_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # file | table | data_lake_path | metric
    kind: Mapped[str | None] = mapped_column(String(30))
    uri: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict | None] = mapped_column(JSONB)

    execution: Mapped["Execution"] = relationship("Execution", back_populates="artifacts")


class RuntimeParameter(TimestampMixin, Base):
    """Effective parameter values used for a given execution (audit of what actually ran)."""

    __tablename__ = "runtime_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(default=False)

    execution: Mapped["Execution"] = relationship(
        "Execution", back_populates="runtime_parameters"
    )
