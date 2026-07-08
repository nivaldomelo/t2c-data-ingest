from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RuntimeLibraryIn(BaseModel):
    package: str | None = None
    version: str | None = None
    package_spec: str | None = None
    active: bool = True
    note: str | None = None


class RuntimeLibraryUpdate(BaseModel):
    package_version: str | None = None
    package_spec: str | None = None
    active: bool | None = None
    note: str | None = None


class RuntimeLibraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    package_name: str
    package_version: str | None = None
    package_spec: str
    source: str
    active: bool
    note: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class RuntimeBuildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    build_version: str
    image_name: str
    image_tag: str
    image_full_name: str
    status: str
    is_active: bool
    jobs_snapshot_path: str | None = None
    dockerfile_path: str | None = None
    context_path: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    created_by: str | None = None
    created_at: datetime


class RuntimeBuildDetailOut(RuntimeBuildOut):
    requirements_snapshot: str | None = None
    build_logs: str | None = None


class RuntimeValidationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    runtime_build_id: int | None = None
    validation_type: str
    status: str
    worker_count_expected: int | None = None
    worker_count_detected: int | None = None
    libraries_checked: Any = None
    workers_result: Any = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime


class RuntimeValidationDetailOut(RuntimeValidationOut):
    logs: str | None = None


class RuntimeValidateRequest(BaseModel):
    validation_type: str = "distributed"  # distributed | libraries
    runtime_build_id: int | None = None


class RequirementsOut(BaseModel):
    content: str
    library_count: int


class RuntimeSummary(BaseModel):
    active_libraries: int = 0
    active_build: str | None = None
    workers_expected: int = 0
    last_validation_status: str | None = None
    last_validation_at: datetime | None = None
