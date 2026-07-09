from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base


def slugify(name: str) -> str:
    s = (name or "").strip().lower()
    # Transliterate accents (produção -> producao) before slugging.
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_t2c_data_ingest_tags_slug"),
        Index("idx_t2c_data_ingest_tags_name", "name"),
        Index("idx_t2c_data_ingest_tags_active", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by: Mapped[int | None] = mapped_column(Integer)
    updated_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobTag(Base):
    __tablename__ = "job_tags"
    __table_args__ = (
        UniqueConstraint("job_id", "tag_id", name="uq_t2c_data_ingest_job_tags_job_tag"),
        Index("idx_t2c_data_ingest_job_tags_job_id", "job_id"),
        Index("idx_t2c_data_ingest_job_tags_tag_id", "tag_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job_definitions.id", ondelete="CASCADE"), nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
