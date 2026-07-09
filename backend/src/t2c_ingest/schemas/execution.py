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
    trigger_type: str = "manual"
    schedule_id: int | None = None
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


class ExecutionConnectionInfo(BaseModel):
    """Source/target connection used in the run (parsed from logs; never includes secrets)."""

    name: str | None = None
    type: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    test_status: str | None = None


class IngestSummaryOut(BaseModel):
    """Structured view of the worker's INGEST_SUMMARY line (fields may be null if truncated)."""

    table: str | None = None
    tipo: str | None = None
    incr_col: str | None = None
    watermark_anterior: str | None = None
    watermark_novo: str | None = None
    lidos: int | None = None
    gravados: int | None = None
    status: str | None = None


class ExecutionDetailOut(ExecutionOut):
    error_trace: str | None = None
    # Mirror of target_type ("job" | "pipeline") for the UI.
    execution_type: str | None = None
    # Populated when trigger_type == "schedule".
    schedule_name: str | None = None
    scheduled_for: datetime | None = None
    triggered_at: datetime | None = None
    # Populated when the run came from a pipeline (resolved via pipeline_step_executions).
    pipeline_name: str | None = None
    pipeline_execution_id: int | None = None
    step_name: str | None = None
    step_order: int | None = None
    # Structured metadata parsed from the logs (fallback when not persisted).
    source_connection: ExecutionConnectionInfo | None = None
    target_connection: ExecutionConnectionInfo | None = None
    ingest_summary: IngestSummaryOut | None = None
    records_read: int | None = None
    records_written: int | None = None
    logs: list[ExecutionLogOut] = []
    artifacts: list[ExecutionArtifactOut] = []
    runtime_parameters: list[RuntimeParameterOut] = []
