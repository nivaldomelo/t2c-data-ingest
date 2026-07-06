from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from t2c_ingest.models.job import JOB_TYPES


class JobBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    type: str
    script_path: str | None = None
    main_class: str | None = None
    sql_statement: str | None = None
    arguments: list | None = None
    env_vars: dict | None = None
    cluster_id: int | None = None
    engine: str | None = None
    timeout_seconds: int | None = None
    is_active: bool = True

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in JOB_TYPES:
            raise ValueError(f"type must be one of {JOB_TYPES}")
        return v


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    script_path: str | None = None
    main_class: str | None = None
    sql_statement: str | None = None
    arguments: list | None = None
    env_vars: dict | None = None
    cluster_id: int | None = None
    engine: str | None = None
    timeout_seconds: int | None = None
    is_active: bool | None = None


class JobOut(JobBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class JobRunRequest(BaseModel):
    parameters: dict | None = None
