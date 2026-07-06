from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.execution import Execution
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.pipeline import PipelineDefinition
from t2c_ingest.schemas.dashboard import DashboardSummary, RecentFailure

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> DashboardSummary:
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

    jobs_total = db.scalar(select(func.count(JobDefinition.id))) or 0
    pipelines_total = db.scalar(select(func.count(PipelineDefinition.id))) or 0
    execs_today = (
        db.scalar(select(func.count(Execution.id)).where(Execution.created_at >= day_ago)) or 0
    )
    success_today = (
        db.scalar(
            select(func.count(Execution.id)).where(
                Execution.created_at >= day_ago, Execution.status == "success"
            )
        )
        or 0
    )
    failed_today = (
        db.scalar(
            select(func.count(Execution.id)).where(
                Execution.created_at >= day_ago,
                Execution.status.in_(["failed", "timeout"]),
            )
        )
        or 0
    )
    running = (
        db.scalar(select(func.count(Execution.id)).where(Execution.status == "running")) or 0
    )
    avg_duration = db.scalar(
        select(func.avg(Execution.duration_seconds)).where(Execution.status == "success")
    )

    return DashboardSummary(
        jobs_total=jobs_total,
        pipelines_total=pipelines_total,
        executions_today=execs_today,
        executions_success_today=success_today,
        executions_failed_today=failed_today,
        jobs_running=running,
        avg_duration_seconds=float(avg_duration) if avg_duration is not None else None,
    )


@router.get("/recent-failures", response_model=list[RecentFailure])
def recent_failures(
    limit: int = 10,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> list[RecentFailure]:
    rows = db.scalars(
        select(Execution)
        .where(Execution.status.in_(["failed", "timeout"]))
        .order_by(Execution.id.desc())
        .limit(max(1, min(limit, 50)))
    ).all()
    return [
        RecentFailure(
            execution_id=r.id,
            target_name=r.target_name,
            status=r.status,
            finished_at=r.finished_at.isoformat() if r.finished_at else None,
            final_message=r.final_message,
        )
        for r in rows
    ]
