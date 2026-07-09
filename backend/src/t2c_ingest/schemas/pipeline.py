from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PipelineBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    domain: str | None = None
    layer: str | None = None
    group_name: str | None = None
    tags: list[str] | None = None
    default_parameters: dict | None = None
    technical_owner: str | None = None
    is_active: bool = True


class PipelineCreate(PipelineBase):
    pass


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    domain: str | None = None
    layer: str | None = None
    group_name: str | None = None
    tags: list[str] | None = None
    default_parameters: dict | None = None
    technical_owner: str | None = None
    is_active: bool | None = None


class PipelineStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int
    step_key: str | None = None
    label: str | None = None
    job_id: int | None = None
    run_if: str = "success"
    active: bool = True


class PipelineOut(PipelineBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    steps_count: int = 0


class PipelineDetailOut(PipelineOut):
    dependencies_count: int = 0
    last_execution_id: int | None = None
    last_status: str | None = None
    last_finished_at: datetime | None = None
    avg_duration_seconds: float | None = None
    executions_total: int = 0


# ── Graph ──
class GraphNode(BaseModel):
    step_key: str
    job_id: int
    label: str | None = None
    position: dict | None = None  # {x, y}
    run_if: str = "success"
    retry_count: int = 0
    timeout_seconds: int | None = None
    parameters: dict | None = None
    active: bool = True


class GraphEdge(BaseModel):
    source_step_key: str
    target_step_key: str
    dependency_type: str = "success"


class GraphPayload(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Executions ──
class PipelineStepExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_id: int
    job_id: int
    execution_id: int | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    message: str | None = None


class PipelineExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int
    status: str
    trigger_type: str
    triggered_by: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    message: str | None = None
    created_at: datetime


class PipelineExecutionDetailOut(PipelineExecutionOut):
    steps: list[PipelineStepExecutionOut] = Field(default_factory=list)


# ── Live graph status (for the builder in "acompanhamento" mode) ──
class GraphStatusNode(BaseModel):
    step_id: int
    step_key: str | None = None
    job_id: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    message: str | None = None


class GraphStatusEdge(BaseModel):
    source_step_id: int
    target_step_id: int
    status: str  # waiting | released | success | blocked | skipped


class GraphStatus(BaseModel):
    pipeline_execution_id: int
    pipeline_id: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    nodes: list[GraphStatusNode] = Field(default_factory=list)
    edges: list[GraphStatusEdge] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    time: datetime
    step_id: int
    job_id: int
    event: str  # iniciado | sucesso | erro | ignorado | ...
    status: str


class StepLogLine(BaseModel):
    level: str
    message: str


class StepLogs(BaseModel):
    step_execution_id: int
    execution_id: int | None = None
    status: str
    message: str | None = None
    lines: list[StepLogLine] = Field(default_factory=list)
