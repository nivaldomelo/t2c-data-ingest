from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base
from t2c_ingest.models.common import TimestampMixin

# python | spark_python | spark_sql | spark_submit
JOB_TYPES = ("python", "spark_python", "spark_sql", "spark_submit")


class JobDefinition(TimestampMixin, Base):
    """A single runnable unit (Python or Spark)."""

    __tablename__ = "job_definitions"
    __table_args__ = (UniqueConstraint("name", name="uq_ingest_job_definitions_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    script_path: Mapped[str | None] = mapped_column(String(500))
    # For spark_submit (JVM) or spark_sql inline statement.
    main_class: Mapped[str | None] = mapped_column(String(255))
    sql_statement: Mapped[str | None] = mapped_column(Text)
    arguments: Mapped[list | None] = mapped_column(JSONB)
    env_vars: Mapped[dict | None] = mapped_column(JSONB)
    cluster_id: Mapped[int | None] = mapped_column(
        ForeignKey("clusters.id", ondelete="SET NULL"), index=True
    )
    # Optional reusable DB connection (see features/connections). Not required yet.
    connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL"), index=True
    )
    # Optional source/target connections (e.g. MySQL -> PostgreSQL jobs).
    source_connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL"), index=True
    )
    target_connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL"), index=True
    )
    default_parameters: Mapped[dict | None] = mapped_column(JSONB)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Max simultaneous queued/running executions for this job (0 = unlimited). Scheduler skips
    # a slot when the limit is reached, preventing overlapping scheduled runs from piling up.
    max_active_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Optional link to a controle.t2c_data_controle_ingestao record (cross-schema; no FK).
    ingestion_control_id: Mapped[int | None] = mapped_column(Integer)
    # Declarative destination (DEST-1). When set, the runner resolves it and injects the target
    # config; legacy target args become optional. No FK to keep it decoupled/soft.
    destination_id: Mapped[int | None] = mapped_column(Integer)
    # python_worker | spark_cluster (defaults derived from type when null)
    engine: Mapped[str | None] = mapped_column(String(20))
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(255))
    # Soft delete: the job leaves the active listing but is never hard-deleted; its code is
    # archived (see features/jobs/archive_service) and the path recorded here.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255))
    delete_reason: Mapped[str | None] = mapped_column(Text)
    archived_code_path: Mapped[str | None] = mapped_column(String(700))
