from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
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
    # python_worker | spark_cluster (defaults derived from type when null)
    engine: Mapped[str | None] = mapped_column(String(20))
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(255))
