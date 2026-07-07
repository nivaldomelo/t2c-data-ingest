from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from t2c_ingest.models.schedule import SCHEDULE_TYPES


class ScheduleBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    schedule_type: str = "cron"
    cron_expression: str | None = None
    timezone: str = "America/Sao_Paulo"
    start_at: datetime | None = None
    end_at: datetime | None = None
    parameters: dict | None = None
    active: bool = True

    @field_validator("schedule_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in SCHEDULE_TYPES:
            raise ValueError(f"schedule_type deve ser um de {SCHEDULE_TYPES}")
        return v


class ScheduleCreate(ScheduleBase):
    # Required for POST /job-schedules; ignored by POST /jobs/{job_id}/schedules (uses path).
    job_id: int | None = None


class ScheduleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    schedule_type: str | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    parameters: dict | None = None
    active: bool | None = None


class ScheduleOut(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    job_name: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_status: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ScheduleRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    job_id: int
    execution_id: int | None = None
    scheduled_for: datetime
    triggered_at: datetime | None = None
    status: str
    message: str | None = None
    created_at: datetime


class CronValidateRequest(BaseModel):
    cron_expression: str
    timezone: str = "America/Sao_Paulo"


class CronValidateResponse(BaseModel):
    valid: bool
    error: str | None = None
    next_runs: list[str] = Field(default_factory=list)


class ScheduleSummary(BaseModel):
    total: int
    active: int
    inactive: int
    next_runs_today: int
    last_error: int
