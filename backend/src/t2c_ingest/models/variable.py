from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base

# string | integer | decimal | boolean | date | datetime | json | secret
VARIABLE_TYPES = ("string", "integer", "decimal", "boolean", "date", "datetime", "json", "secret")
# global | job | pipeline | environment
VARIABLE_SCOPES = ("global", "job", "pipeline", "environment")
ENVIRONMENTS = ("local", "dev", "hml", "prd")


class Variable(Base):
    """A reusable parameter for jobs/pipelines. Secret values are stored encrypted and never
    returned by the API."""

    __tablename__ = "variables"
    __table_args__ = (
        Index("idx_t2c_data_ingest_variables_name", "name"),
        Index("idx_t2c_data_ingest_variables_scope", "scope"),
        Index("idx_t2c_data_ingest_variables_environment", "environment"),
        Index("idx_t2c_data_ingest_variables_active", "active"),
        Index("idx_t2c_data_ingest_variables_is_secret", "is_secret"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # For secrets, holds the encrypted blob; for others, the plaintext value.
    value: Mapped[str | None] = mapped_column(Text)
    variable_type: Mapped[str] = mapped_column(String(30), nullable=False, default="string")
    scope: Mapped[str] = mapped_column(String(30), nullable=False, default="global")
    environment: Mapped[str | None] = mapped_column(String(30))
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by: Mapped[int | None] = mapped_column(Integer)
    updated_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobVariable(Base):
    """Association of a variable to a job (prepared for future job-scoped injection)."""

    __tablename__ = "job_variables"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variable_id: Mapped[int] = mapped_column(
        ForeignKey("variables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    override_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
