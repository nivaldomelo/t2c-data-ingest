from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base
from t2c_ingest.models.common import TimestampMixin

# postgres | mysql
CONNECTION_TYPES = ("postgres", "mysql")
# success | failed | not_tested
TEST_STATUSES = ("success", "failed", "not_tested")

DEFAULT_PORTS = {"postgres": 5432, "mysql": 3306}


class Connection(TimestampMixin, Base):
    """A reusable database connection for jobs/pipelines. The password is stored encrypted
    and never returned by the API."""

    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("name", name="uq_ingest_connections_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    connection_type: Mapped[str] = mapped_column(String(20), nullable=False)
    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int | None] = mapped_column(Integer)
    database_name: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    schema_name: Mapped[str | None] = mapped_column(String(255))
    extra_params: Mapped[dict | None] = mapped_column(JSONB)
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_tested")
    last_test_message: Mapped[str | None] = mapped_column(Text)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(255))
