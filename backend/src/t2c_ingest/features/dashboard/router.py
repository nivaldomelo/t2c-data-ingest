from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.core.db import get_db
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.cluster import Cluster
from t2c_ingest.models.execution import Execution
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.pipeline import PipelineDefinition, PipelineExecution
from t2c_ingest.models.schedule import JobSchedule
from t2c_ingest.schemas.dashboard import (
    DashboardSummary,
    OpCluster,
    OpExecution,
    OperationalDashboard,
    OpRunningPipeline,
    OpSchedule,
    OpSlowJob,
    OpZeroRecord,
    RecentFailure,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_RUNNING = ("queued", "running")
_FAILED = ("failed", "timeout")


def _records(final_message: str | None) -> tuple[int | None, int | None]:
    """Extract lidos/gravados from a stored INGEST_SUMMARY line (worker saves it in final_message)."""
    if not final_message:
        return None, None
    r = re.search(r"lidos=(\d+)", final_message)
    g = re.search(r"gravados=(\d+)", final_message)
    return (int(r.group(1)) if r else None, int(g.group(1)) if g else None)


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


def _op_exec(e: Execution) -> OpExecution:
    return OpExecution(id=e.id, name=e.target_name, status=e.status, engine=e.engine,
                       trigger_type=e.trigger_type, started_at=e.started_at,
                       finished_at=e.finished_at, duration_seconds=e.duration_seconds)


@router.get("/operational", response_model=OperationalDashboard)
def operational(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> OperationalDashboard:
    # Cache the (expensive: ~20 queries + Spark HTTP) payload briefly so many pollers across
    # tabs/users collapse into one computation. TTL well under the frontend refetch interval.
    from t2c_ingest.core.cache import cached

    return cached("dashboard:operational", 15.0, lambda: _operational_compute(db))


def _operational_compute(db: Session) -> OperationalDashboard:
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    def count(stmt) -> int:
        return db.scalar(stmt) or 0

    # Running now.
    running_jobs = db.scalars(
        select(Execution).where(Execution.status.in_(_RUNNING), Execution.target_type == "job",
                                Execution.parent_execution_id.is_(None)).order_by(Execution.id.desc()).limit(20)
    ).all()
    running_pes = db.scalars(
        select(PipelineExecution).where(PipelineExecution.status == "running").order_by(PipelineExecution.id.desc()).limit(20)
    ).all()
    pipe_names = {p.id: p.name for p in db.scalars(select(PipelineDefinition)).all()}

    # Today / 7d aggregates.
    executions_today = count(select(func.count(Execution.id)).where(Execution.created_at >= day_ago))
    success_today = count(select(func.count(Execution.id)).where(Execution.created_at >= day_ago, Execution.status == "success"))
    failed_today = count(select(func.count(Execution.id)).where(Execution.created_at >= day_ago, Execution.status.in_(_FAILED)))
    failures_7d = count(select(func.count(Execution.id)).where(Execution.created_at >= week_ago, Execution.status.in_(_FAILED)))
    jobs_with_error_7d = count(select(func.count(func.distinct(Execution.job_id))).where(Execution.created_at >= week_ago, Execution.status.in_(_FAILED)))
    pipelines_with_error_7d = count(select(func.count(PipelineExecution.id)).where(PipelineExecution.started_at >= week_ago, PipelineExecution.status.in_(_FAILED)))
    avg_duration = db.scalar(select(func.avg(Execution.duration_seconds)).where(Execution.status == "success", Execution.created_at >= month_ago))

    status_rows = db.execute(
        select(Execution.status, func.count(Execution.id)).where(Execution.created_at >= week_ago).group_by(Execution.status)
    ).all()
    status_distribution = {s: c for s, c in status_rows}

    # Recent.
    recent = db.scalars(select(Execution).where(Execution.parent_execution_id.is_(None)).order_by(Execution.id.desc()).limit(8)).all()
    recent_fail = db.scalars(select(Execution).where(Execution.status.in_(_FAILED)).order_by(Execution.id.desc()).limit(6)).all()

    # Schedules overdue / upcoming.
    sched_rows = db.scalars(select(JobSchedule).where(JobSchedule.active.is_(True))).all()
    job_names = {j.id: j.name for j in db.scalars(select(JobDefinition)).all()}
    overdue, upcoming = [], []
    for s in sched_rows:
        if not s.next_run_at:
            continue
        item = OpSchedule(id=s.id, name=s.name, job_id=s.job_id, job_name=job_names.get(s.job_id),
                          next_run_at=s.next_run_at)
        if s.next_run_at < now:
            item.minutes_late = int((now - s.next_run_at).total_seconds() // 60)
            overdue.append(item)
        else:
            upcoming.append(item)
    overdue.sort(key=lambda x: x.minutes_late or 0, reverse=True)
    upcoming.sort(key=lambda x: x.next_run_at or now)

    # Records + zero-record + slow jobs from today's successful job executions (bounded scan).
    todays_ok = db.scalars(
        select(Execution).where(Execution.created_at >= day_ago, Execution.status == "success",
                                Execution.target_type == "job").order_by(Execution.id.desc()).limit(500)
    ).all()
    read_total = written_total = 0
    zero_jobs = []
    for e in todays_ok:
        lidos, gravados = _records(e.final_message)
        if lidos is not None:
            read_total += lidos
        if gravados is not None:
            written_total += gravados
        if lidos == 0 and gravados == 0 and len(zero_jobs) < 10:
            zero_jobs.append(OpZeroRecord(execution_id=e.id, name=e.target_name, finished_at=e.finished_at))

    avg_by_job = {}
    for jid, avg in db.execute(
        select(Execution.job_id, func.avg(Execution.duration_seconds)).where(
            Execution.status == "success", Execution.job_id.is_not(None), Execution.created_at >= month_ago
        ).group_by(Execution.job_id)
    ).all():
        if avg:
            avg_by_job[jid] = float(avg)
    slow = []
    for e in todays_ok:
        avg = avg_by_job.get(e.job_id)
        if avg and avg > 0 and e.duration_seconds and e.duration_seconds >= 5 and e.duration_seconds > 1.5 * avg:
            slow.append(OpSlowJob(execution_id=e.id, name=e.target_name, duration_seconds=e.duration_seconds,
                                  avg_seconds=round(avg, 1), factor=round(e.duration_seconds / avg, 1),
                                  finished_at=e.finished_at))
    slow.sort(key=lambda x: x.factor or 0, reverse=True)

    # Cluster (live).
    cluster = None
    c0 = db.scalar(select(Cluster).order_by(Cluster.id).limit(1))
    if c0:
        from t2c_ingest.features.clusters import state as cluster_state
        summ = cluster_state.summarize(cluster_state.fetch_master_state())
        cluster = OpCluster(
            name=c0.name, status="active" if summ.get("reachable") else "unreachable",
            workers_detected=summ.get("workers", 0), workers_expected=c0.expected_workers or settings.spark_expected_workers,
            cores_total=summ.get("cores", 0), memory_total=summ.get("memory"),
        )

    return OperationalDashboard(
        generated_at=now,
        running_jobs=len(running_jobs), running_pipelines=len(running_pes),
        executions_today=executions_today, success_today=success_today, failed_today=failed_today,
        failures_7d=failures_7d, jobs_with_error_7d=jobs_with_error_7d, pipelines_with_error_7d=pipelines_with_error_7d,
        records_read_today=read_total, records_written_today=written_total,
        avg_duration_seconds=float(avg_duration) if avg_duration is not None else None,
        status_distribution=status_distribution,
        running_jobs_list=[_op_exec(e) for e in running_jobs],
        running_pipelines_list=[OpRunningPipeline(id=p.id, pipeline_id=p.pipeline_id, name=pipe_names.get(p.pipeline_id), started_at=p.started_at) for p in running_pes],
        recent_executions=[_op_exec(e) for e in recent],
        recent_failures=[_op_exec(e) for e in recent_fail],
        schedules_overdue=overdue[:8], schedules_upcoming=upcoming[:6],
        zero_record_jobs=zero_jobs, slow_jobs=slow[:6], cluster=cluster,
    )
