from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from t2c_ingest.models.base import Base
from t2c_ingest.models.common import TimestampMixin


class Cluster(TimestampMixin, Base):
    """A compute target for jobs. Starts as ``local_docker`` Spark; future: kubernetes/eks/emr."""

    __tablename__ = "clusters"
    __table_args__ = (UniqueConstraint("name", name="uq_ingest_clusters_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # local_docker | kubernetes | eks | emr
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="local_docker")
    spark_master_url: Mapped[str | None] = mapped_column(String(255))
    # active | inactive | unreachable
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    worker_count: Mapped[int | None] = mapped_column(Integer)
    total_cores: Mapped[int | None] = mapped_column(Integer)
    total_memory: Mapped[str | None] = mapped_column(String(30))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(255))
