from __future__ import annotations

from pydantic import BaseModel


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
