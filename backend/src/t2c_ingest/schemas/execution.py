from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExecutionLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_id: int | None = None
    seq: int
    level: str
    message: str
    logged_at: datetime | None = None


class ExecutionArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: str | None = None
    uri: str | None = None
    size_bytes: int | None = None
    meta: dict | None = None


class RuntimeParameterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: str | None = None
    is_secret: bool = False


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_type: str
    job_id: int | None = None
    pipeline_id: int | None = None
    target_name: str | None = None
    job_type: str | None = None
    status: str
    engine: str | None = None
    cluster_id: int | None = None
    parameters: dict | None = None
    triggered_by: str | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    final_message: str | None = None
    parent_execution_id: int | None = None
    step_id: int | None = None
    created_at: datetime


class ExecutionDetailOut(ExecutionOut):
    error_trace: str | None = None
    logs: list[ExecutionLogOut] = []
    artifacts: list[ExecutionArtifactOut] = []
    runtime_parameters: list[RuntimeParameterOut] = []
