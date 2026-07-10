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
    expected_workers: int | None = None
    last_checked_at: datetime | None = None
    last_validation_status: str | None = None
    runtime_image: str | None = None
    spark_version: str | None = None
    python_version: str | None = None
    java_version: str | None = None
    scala_version: str | None = None
    environment: str | None = None
    environment_label: str | None = None
    live: bool = False
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ClusterConnectionResult(BaseModel):
    reachable: bool
    master_url: str | None = None
    message: str
    workers_detected: int | None = None


class ClusterWorker(BaseModel):
    name: str
    status: str
    host: str | None = None
    cores: int | None = None
    memory: str | None = None
    last_heartbeat_at: datetime | None = None


class ClusterWorkersOut(BaseModel):
    cluster_id: int
    workers_expected: int
    workers_detected: int
    workers: list[ClusterWorker] = Field(default_factory=list)


class ClustersSummary(BaseModel):
    total_clusters: int = 0
    active_clusters: int = 0
    workers_total: int = 0
    cores_total: int = 0
    memory_total: str | None = None
    last_validation_status: str | None = None


class ClusterValidationOut(BaseModel):
    id: int
    validation_type: str
    status: str
    worker_count_expected: int | None = None
    worker_count_detected: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
