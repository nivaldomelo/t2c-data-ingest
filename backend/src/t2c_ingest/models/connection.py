from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base
from t2c_ingest.models.common import TimestampMixin

# postgres | mysql | s3
CONNECTION_TYPES = ("postgres", "mysql", "s3")
# success | failed | not_tested
TEST_STATUSES = ("success", "failed", "not_tested")
# S3 authentication modes.
S3_AUTH_MODES = ("access_key", "iam_role", "instance_profile", "environment")

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
    # Non-secret, type-specific config (S3: aws_region, bucket_name, base_prefix, default_layer,
    # auth_mode, role_arn, external_id, endpoint_url). Secrets live in the *_encrypted columns.
    extra_params: Mapped[dict | None] = mapped_column(JSONB)
    # S3 credentials (access_key mode) — encrypted at rest (Fernet), never returned by the API.
    aws_access_key_id_encrypted: Mapped[str | None] = mapped_column(Text)
    aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text)
    aws_session_token_encrypted: Mapped[str | None] = mapped_column(Text)
    # Whether this connection may be used as a source (read) and/or destination (write).
    can_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    can_write: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_tested")
    last_test_message: Mapped[str | None] = mapped_column(Text)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(255))
