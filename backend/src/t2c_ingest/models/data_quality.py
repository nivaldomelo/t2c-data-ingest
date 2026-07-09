from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base


class DqResult(Base):
    """Data-quality evaluation of one execution (derived from INGEST_SUMMARY + logs)."""

    __tablename__ = "dq_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int | None] = mapped_column(Integer, index=True)
    job_id: Mapped[int | None] = mapped_column(Integer)
    job_name: Mapped[str | None] = mapped_column(String(200))
    table_name: Mapped[str | None] = mapped_column(Text)
    tipo_ingestao: Mapped[str | None] = mapped_column(String(30))
    records_read: Mapped[int | None] = mapped_column(Integer)
    records_written: Mapped[int | None] = mapped_column(Integer)
    watermark_before: Mapped[str | None] = mapped_column(Text)
    watermark_after: Mapped[str | None] = mapped_column(Text)
    # list of {name, status(pass|warn|fail), detail}
    checks: Mapped[list | None] = mapped_column(JSONB)
    overall: Mapped[str] = mapped_column(String(20), nullable=False, default="pass", server_default="pass")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
