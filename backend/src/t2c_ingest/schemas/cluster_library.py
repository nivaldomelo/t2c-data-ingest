from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LibraryInstallRequest(BaseModel):
    cluster_id: int | None = None
    package: str | None = None
    version: str | None = None
    package_spec: str | None = None
    install_scope: str = "cluster"
    note: str | None = None


class PackageValidateRequest(BaseModel):
    package_spec: str


class PackageValidateResponse(BaseModel):
    valid: bool
    package_name: str | None = None
    version: str | None = None
    normalized_spec: str | None = None
    error: str | None = None


class LibraryActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    library_id: int | None = None
    cluster_id: int | None = None
    action: str
    package_spec: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    command_safe: str | None = None
    error_message: str | None = None
    requested_by: str | None = None
    created_at: datetime


class LibraryActionDetailOut(LibraryActionOut):
    logs: str | None = None


class LibraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cluster_id: int | None = None
    package_name: str
    package_version: str | None = None
    package_spec: str
    source: str
    install_scope: str
    status: str
    active: bool
    note: str | None = None
    installed_at: datetime | None = None
    installed_by: str | None = None
    removed_at: datetime | None = None
    removed_by: str | None = None
    last_action_at: datetime | None = None
    last_action_status: str | None = None
    last_action_message: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class LibraryDetailOut(LibraryOut):
    actions: list[LibraryActionOut] = Field(default_factory=list)


class LibrarySummary(BaseModel):
    installed: int = 0
    success: int = 0
    failed: int = 0
    running: int = 0
    last_installed_at: datetime | None = None
