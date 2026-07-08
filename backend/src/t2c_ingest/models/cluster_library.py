from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base

# pending | queued | installing | installed | failed | removed
LIBRARY_STATUSES = ("pending", "queued", "installing", "installed", "failed", "removed")
# install | uninstall | reinstall | check
LIBRARY_ACTIONS = ("install", "uninstall", "reinstall", "check")
# queued | running | success | failed | cancelled
ACTION_STATUSES = ("queued", "running", "success", "failed", "cancelled")


class ClusterLibrary(Base):
    """A Python package managed through the UI and installed into the worker's environment."""

    __tablename__ = "cluster_libraries"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int | None] = mapped_column(Integer)
    package_name: Mapped[str] = mapped_column(String(200), nullable=False)
    package_version: Mapped[str | None] = mapped_column(String(100))
    package_spec: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="pypi", server_default="pypi")
    install_scope: Mapped[str] = mapped_column(String(30), nullable=False, default="cluster", server_default="cluster")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    note: Mapped[str | None] = mapped_column(Text)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    installed_by: Mapped[str | None] = mapped_column(String(255))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by: Mapped[str | None] = mapped_column(String(255))
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_action_status: Mapped[str | None] = mapped_column(String(30))
    last_action_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class ClusterLibraryAction(Base):
    """One install/uninstall/reinstall/check attempt, with captured logs."""

    __tablename__ = "cluster_library_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    library_id: Mapped[int | None] = mapped_column(Integer, index=True)
    cluster_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    package_spec: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", server_default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    command_safe: Mapped[str | None] = mapped_column(Text)
    logs: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class JobLibrary(Base):
    """Links a job to a library it depends on (prepared for future run-time validation)."""

    __tablename__ = "job_libraries"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    library_id: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
