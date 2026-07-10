from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class BackfillCreate(BaseModel):
    kind: str  # job | pipeline | control_group | control_table
    job_id: int | None = None
    pipeline_id: int | None = None
    from_step_id: int | None = None
    control_group: str | None = None
    table_name: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    reset_watermark: bool = False
    watermark_value: str | None = None
    reason: str | None = None


class BackfillExecLite(BaseModel):
    id: int
    target_name: str | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None


class BackfillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    job_id: int | None = None
    pipeline_id: int | None = None
    from_step_id: int | None = None
    pipeline_execution_id: int | None = None
    control_group: str | None = None
    table_name: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    reset_watermark: bool = False
    watermark_value: str | None = None
    reason: str | None = None
    status: str
    total_targets: int = 0
    succeeded: int = 0
    failed: int = 0
    watermarks_reset: int = 0
    message: str | None = None
    created_by: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    # Label filled by the router (job/pipeline/group name) for the list.
    target_label: str | None = None


class BackfillDetailOut(BackfillOut):
    executions: list[BackfillExecLite] = Field(default_factory=list)
