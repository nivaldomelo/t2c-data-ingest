from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base


class IngestUserAccess(Base):
    """Admin-managed allowlist of who may use the ingest tool.

    Credentials/roles are shared with t2c_data, but access to THIS tool is opt-in: an admin
    grants a user access here (view-only). Admins always have access implicitly and are not
    required to have a row. Emails are stored normalized (lowercase).
    """

    __tablename__ = "user_access"
    __table_args__ = (Index("ix_ingest_user_access_email", "email", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    granted_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
