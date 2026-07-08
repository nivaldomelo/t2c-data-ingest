from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from t2c_ingest.models.base import Base
from t2c_ingest.models.common import TimestampMixin

# bronze | silver | gold | full
PIPELINE_LAYERS = ("bronze", "silver", "gold", "full")
# success | finished | failed | always
DEPENDENCY_TYPES = ("success", "finished", "failed", "always")
PIPELINE_EXEC_STATUSES = (
    "queued", "running", "success", "failed", "cancelled", "skipped", "partial_success",
)


class PipelineDefinition(TimestampMixin, Base):
    """A DAG of jobs (visual builder). Steps + dependencies define execution order."""

    __tablename__ = "pipeline_definitions"
    __table_args__ = (UniqueConstraint("name", name="uq_ingest_pipeline_definitions_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(120))
    layer: Mapped[str | None] = mapped_column(String(20))
    group_name: Mapped[str | None] = mapped_column(String(80))
    tags: Mapped[list | None] = mapped_column(JSONB)
    default_parameters: Mapped[dict | None] = mapped_column(JSONB)
    technical_owner: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(255))

    steps: Mapped[list["PipelineStep"]] = relationship(
        "PipelineStep",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="PipelineStep.order_index",
    )
    dependencies: Mapped[list["PipelineStepDependency"]] = relationship(
        "PipelineStepDependency", cascade="all, delete-orphan"
    )


class PipelineStep(TimestampMixin, Base):
    __tablename__ = "pipeline_steps"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "order_index", name="uq_ingest_pipeline_steps_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str | None] = mapped_column(String(120))
    name: Mapped[str | None] = mapped_column(String(150))
    label: Mapped[str | None] = mapped_column(String(150))
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_definitions.id", ondelete="SET NULL"), index=True
    )
    position_x: Mapped[float | None] = mapped_column(Numeric(12, 2))
    position_y: Mapped[float | None] = mapped_column(Numeric(12, 2))
    run_if: Mapped[str] = mapped_column(String(30), nullable=False, default="success", server_default="success")
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    depends_on: Mapped[list | None] = mapped_column(JSONB)
    stop_on_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    pipeline: Mapped["PipelineDefinition"] = relationship("PipelineDefinition", back_populates="steps")


class PipelineStepDependency(Base):
    __tablename__ = "pipeline_step_dependencies"
    __table_args__ = (
        UniqueConstraint("upstream_step_id", "downstream_step_id", name="uq_ingest_pipeline_dep"),
        Index("ix_ingest_pipeline_dep_pipeline", "pipeline_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_definitions.id", ondelete="CASCADE"), nullable=False
    )
    upstream_step_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_steps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    downstream_step_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_steps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dependency_type: Mapped[str] = mapped_column(String(30), nullable=False, default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PipelineExecution(Base):
    __tablename__ = "pipeline_executions"
    __table_args__ = (Index("ix_ingest_pipeline_exec_pipeline", "pipeline_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    triggered_by: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    step_executions: Mapped[list["PipelineStepExecution"]] = relationship(
        "PipelineStepExecution", cascade="all, delete-orphan"
    )


class PipelineStepExecution(Base):
    __tablename__ = "pipeline_step_executions"
    __table_args__ = (Index("ix_ingest_pipeline_step_exec_parent", "pipeline_execution_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_execution_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_id: Mapped[int] = mapped_column(Integer, nullable=False)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
