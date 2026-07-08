from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from t2c_ingest.models.job import JOB_TYPES
from t2c_ingest.schemas.tag import TagLite


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
    connection_id: int | None = None
    source_connection_id: int | None = None
    target_connection_id: int | None = None
    default_parameters: dict | None = None
    retry_count: int = 0
    ingestion_control_id: int | None = None
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
    connection_id: int | None = None
    source_connection_id: int | None = None
    target_connection_id: int | None = None
    default_parameters: dict | None = None
    retry_count: int | None = None
    ingestion_control_id: int | None = None
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
    tags: list[TagLite] = Field(default_factory=list)
    # Soft-delete bookkeeping (null for active jobs).
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    delete_reason: str | None = None
    archived_code_path: str | None = None


class JobDetailOut(JobOut):
    """Job detail enriched with connection names and execution stats for the overview tab."""

    source_connection_name: str | None = None
    target_connection_name: str | None = None
    executions_total: int = 0
    last_execution_id: int | None = None
    last_status: str | None = None
    last_finished_at: datetime | None = None
    avg_duration_seconds: float | None = None


class JobCodeOut(BaseModel):
    job_id: int
    job_name: str
    script_path: str | None = None
    file_name: str | None = None
    language: str
    content: str
    editable: bool = False
    read_only: bool = True
    # Opaque token for optimistic-lock: returned verbatim and sent back as
    # expected_last_modified_at. Kept as a string so it round-trips without reformatting.
    last_modified_at: str | None = None
    size_bytes: int | None = None


class JobCodeSaveRequest(BaseModel):
    content: str
    expected_last_modified_at: str | None = None
    change_summary: str | None = None


class JobSearchOut(BaseModel):
    """Light job representation for the pipeline builder command palette."""

    id: int
    name: str
    description: str | None = None
    job_type: str
    engine: str | None = None
    active: bool
    tags: list[TagLite] = Field(default_factory=list)


class JobRunRequest(BaseModel):
    parameters: dict | None = None


class JobDeleteRequest(BaseModel):
    reason: str | None = None
    # Reserved for a future admin "forced delete"; ignored (blocked) in this version.
    force: bool = False


class JobDeleteResult(BaseModel):
    success: bool = True
    message: str
    job_id: int
    archived_code_path: str | None = None
