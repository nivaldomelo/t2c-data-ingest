from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DqResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int | None = None
    job_id: int | None = None
    job_name: str | None = None
    table_name: str | None = None
    tipo_ingestao: str | None = None
    records_read: int | None = None
    records_written: int | None = None
    watermark_before: str | None = None
    watermark_after: str | None = None
    checks: Any = None
    overall: str
    created_at: datetime


class DqSummary(BaseModel):
    total_7d: int = 0
    passed_7d: int = 0
    warn_7d: int = 0
    failed_7d: int = 0
    records_read_7d: int = 0
    records_written_7d: int = 0
