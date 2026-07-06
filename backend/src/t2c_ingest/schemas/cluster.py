from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClusterBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    type: str = "local_docker"
    spark_master_url: str | None = None
    worker_count: int | None = None
    total_cores: int | None = None
    total_memory: str | None = None
    is_active: bool = True


class ClusterCreate(ClusterBase):
    pass


class ClusterUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    spark_master_url: str | None = None
    worker_count: int | None = None
    total_cores: int | None = None
    total_memory: str | None = None
    status: str | None = None
    is_active: bool | None = None


class ClusterOut(ClusterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    last_heartbeat_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ClusterConnectionResult(BaseModel):
    reachable: bool
    master_url: str | None = None
    message: str
