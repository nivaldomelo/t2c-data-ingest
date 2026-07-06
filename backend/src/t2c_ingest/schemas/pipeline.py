from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PipelineStepBase(BaseModel):
    order_index: int
    name: str | None = None
    job_id: int | None = None
    parameters: dict | None = None
    depends_on: list[int] | None = None
    stop_on_error: bool = True
    retry_count: int = 0
    timeout_seconds: int | None = None


class PipelineStepCreate(PipelineStepBase):
    pass


class PipelineStepOut(PipelineStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int


class PipelineBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    domain: str | None = None
    layer: str | None = None
    tags: list[str] | None = None
    technical_owner: str | None = None
    is_active: bool = True


class PipelineCreate(PipelineBase):
    steps: list[PipelineStepCreate] = Field(default_factory=list)


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    domain: str | None = None
    layer: str | None = None
    tags: list[str] | None = None
    technical_owner: str | None = None
    is_active: bool | None = None
    steps: list[PipelineStepCreate] | None = None


class PipelineOut(PipelineBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    steps: list[PipelineStepOut] = Field(default_factory=list)
