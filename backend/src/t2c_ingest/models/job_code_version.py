from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base


class JobCodeVersion(Base):
    """History of job source-code edits made through the UI (one row per save)."""

    __tablename__ = "job_code_versions"
    __table_args__ = (Index("ix_ingest_job_code_versions_job_changed", "job_id", "changed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    script_path: Mapped[str] = mapped_column(String(500), nullable=False)
    # created | updated | renamed | deleted | folder_created | folder_deleted
    action: Mapped[str | None] = mapped_column(String(30))
    file_path: Mapped[str | None] = mapped_column(String(700))
    backup_path: Mapped[str | None] = mapped_column(String(700))
    content_hash_before: Mapped[str | None] = mapped_column(String(64))
    content_hash_after: Mapped[str | None] = mapped_column(String(64))
    changed_by: Mapped[str | None] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    change_summary: Mapped[str | None] = mapped_column(Text)
    size_before_bytes: Mapped[int | None] = mapped_column(Integer)
    size_after_bytes: Mapped[int | None] = mapped_column(Integer)
