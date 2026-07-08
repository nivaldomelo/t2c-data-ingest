from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base

# queued | building | success | failed | active | deprecated
BUILD_STATUSES = ("queued", "building", "success", "failed", "active", "deprecated")
# queued | running | success | failed
VALIDATION_STATUSES = ("queued", "running", "success", "failed")
# libraries | distributed
VALIDATION_TYPES = ("libraries", "distributed")


class RuntimeLibrary(Base):
    """A Python dependency of the cluster runtime image (the manifest for requirements.txt)."""

    __tablename__ = "runtime_libraries"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_name: Mapped[str] = mapped_column(String(200), nullable=False)
    package_version: Mapped[str | None] = mapped_column(String(100))
    package_spec: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="pypi", server_default="pypi")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class RuntimeBuild(Base):
    """One build of the cluster runtime image (libraries + jobs baked in), versioned."""

    __tablename__ = "runtime_builds"

    id: Mapped[int] = mapped_column(primary_key=True)
    build_version: Mapped[str] = mapped_column(String(100), nullable=False)
    image_name: Mapped[str] = mapped_column(String(300), nullable=False)
    image_tag: Mapped[str] = mapped_column(String(150), nullable=False)
    image_full_name: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", server_default="queued")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    requirements_snapshot: Mapped[str | None] = mapped_column(Text)
    jobs_snapshot_path: Mapped[str | None] = mapped_column(Text)
    dockerfile_path: Mapped[str | None] = mapped_column(Text)
    context_path: Mapped[str | None] = mapped_column(Text)
    build_logs: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RuntimeValidation(Base):
    """A cluster validation run (libraries available on all workers / distributed execution)."""

    __tablename__ = "runtime_validations"

    id: Mapped[int] = mapped_column(primary_key=True)
    runtime_build_id: Mapped[int | None] = mapped_column(Integer)
    validation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", server_default="queued")
    worker_count_expected: Mapped[int | None] = mapped_column(Integer)
    worker_count_detected: Mapped[int | None] = mapped_column(Integer)
    libraries_checked: Mapped[dict | None] = mapped_column(JSONB)
    workers_result: Mapped[dict | None] = mapped_column(JSONB)
    logs: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
