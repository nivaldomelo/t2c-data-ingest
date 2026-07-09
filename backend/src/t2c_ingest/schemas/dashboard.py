from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    jobs_total: int
    pipelines_total: int
    executions_today: int
    executions_success_today: int
    executions_failed_today: int
    jobs_running: int
    avg_duration_seconds: float | None = None


class RecentFailure(BaseModel):
    execution_id: int
    target_name: str | None
    status: str
    finished_at: str | None
    final_message: str | None


# ── Operational dashboard ──
class OpExecution(BaseModel):
    id: int
    name: str | None = None
    status: str
    engine: str | None = None
    trigger_type: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None


class OpRunningPipeline(BaseModel):
    id: int
    pipeline_id: int | None = None
    name: str | None = None
    started_at: datetime | None = None


class OpSchedule(BaseModel):
    id: int
    name: str
    job_id: int | None = None
    job_name: str | None = None
    next_run_at: datetime | None = None
    minutes_late: int | None = None


class OpSlowJob(BaseModel):
    execution_id: int
    name: str | None = None
    duration_seconds: int | None = None
    avg_seconds: float | None = None
    factor: float | None = None
    finished_at: datetime | None = None


class OpZeroRecord(BaseModel):
    execution_id: int
    name: str | None = None
    finished_at: datetime | None = None


class OpCluster(BaseModel):
    name: str | None = None
    status: str | None = None
    workers_detected: int = 0
    workers_expected: int = 0
    cores_total: int = 0
    memory_total: str | None = None


class OperationalDashboard(BaseModel):
    generated_at: datetime
    running_jobs: int = 0
    running_pipelines: int = 0
    executions_today: int = 0
    success_today: int = 0
    failed_today: int = 0
    failures_7d: int = 0
    jobs_with_error_7d: int = 0
    pipelines_with_error_7d: int = 0
    records_read_today: int = 0
    records_written_today: int = 0
    avg_duration_seconds: float | None = None
    status_distribution: dict[str, int] = Field(default_factory=dict)
    running_jobs_list: list[OpExecution] = Field(default_factory=list)
    running_pipelines_list: list[OpRunningPipeline] = Field(default_factory=list)
    recent_executions: list[OpExecution] = Field(default_factory=list)
    recent_failures: list[OpExecution] = Field(default_factory=list)
    schedules_overdue: list[OpSchedule] = Field(default_factory=list)
    schedules_upcoming: list[OpSchedule] = Field(default_factory=list)
    zero_record_jobs: list[OpZeroRecord] = Field(default_factory=list)
    slow_jobs: list[OpSlowJob] = Field(default_factory=list)
    cluster: OpCluster | None = None
