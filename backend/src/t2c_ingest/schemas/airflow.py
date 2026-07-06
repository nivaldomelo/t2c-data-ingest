from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AirflowTaskBase(BaseModel):
    task_id: str
    operator: str | None = None
    upstream_tasks: list[str] | None = None
    mapped_step_id: int | None = None
    notes: str | None = None


class AirflowTaskOut(AirflowTaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dag_import_id: int


class AirflowDagBase(BaseModel):
    dag_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    schedule: str | None = None
    tags: list[str] | None = None
    file_path: str | None = None
    migration_status: str = "nao_analisada"
    mapped_pipeline_id: int | None = None
    technical_notes: str | None = None


class AirflowDagCreate(AirflowDagBase):
    tasks: list[AirflowTaskBase] = Field(default_factory=list)


class AirflowDagUpdate(BaseModel):
    description: str | None = None
    schedule: str | None = None
    tags: list[str] | None = None
    file_path: str | None = None
    migration_status: str | None = None
    mapped_pipeline_id: int | None = None
    technical_notes: str | None = None


class AirflowDagOut(AirflowDagBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    tasks: list[AirflowTaskOut] = Field(default_factory=list)
