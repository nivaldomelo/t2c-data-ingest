from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.features.auth_bridge.deps import CurrentUser
from t2c_ingest.models.execution import Execution, RuntimeParameter
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.pipeline import PipelineDefinition
from t2c_ingest.services.audit import record_audit


def _engine_for_job(job: JobDefinition) -> str:
    if job.engine:
        return job.engine
    return "python_worker" if job.type == "python" else "spark_cluster"


def active_execution_count(db: Session, job_id: int) -> int:
    """Number of queued/running executions for a job (for concurrency limiting)."""
    return int(db.scalar(
        select(func.count(Execution.id)).where(
            Execution.job_id == job_id,
            Execution.status.in_(("queued", "running")),
        )
    ) or 0)


def create_job_execution(
    db: Session,
    *,
    job: JobDefinition,
    triggered_by: str | None,
    trigger_type: str = "manual",
    schedule_id: int | None = None,
    parameters: dict | None = None,
    attempt: int = 1,
) -> Execution:
    """Core: register a queued job execution (no CurrentUser dependency).

    Used by the API (manual/schedule run) and the scheduler. The worker/Spark cluster picks
    up the queued execution and runs it."""
    if not job.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Job is inactive and cannot be run"
        )
    now = datetime.now(timezone.utc)
    execution = Execution(
        target_type="job",
        job_id=job.id,
        target_name=job.name,
        job_type=job.type,
        status="queued",
        trigger_type=trigger_type,
        schedule_id=schedule_id,
        engine=_engine_for_job(job),
        cluster_id=job.cluster_id,
        parameters=parameters or {},
        triggered_by=triggered_by,
        attempt=attempt,
        queued_at=now,
    )
    db.add(execution)
    db.flush()
    for key, value in (parameters or {}).items():
        db.add(
            RuntimeParameter(execution_id=execution.id, key=str(key), value=_stringify(value))
        )
    return execution


def enqueue_job_execution(
    db: Session,
    *,
    job: JobDefinition,
    user: CurrentUser,
    parameters: dict | None = None,
    trigger_type: str = "manual",
    schedule_id: int | None = None,
) -> Execution:
    execution = create_job_execution(
        db,
        job=job,
        triggered_by=user.email,
        trigger_type=trigger_type,
        schedule_id=schedule_id,
        parameters=parameters,
    )
    record_audit(
        db,
        action="ingest.execution.enqueued",
        user=user,
        entity_type="execution",
        entity_id=execution.id,
        detail={"target_type": "job", "job_id": job.id, "engine": execution.engine, "trigger_type": trigger_type},
    )
    return execution


def enqueue_pipeline_execution(
    db: Session,
    *,
    pipeline: PipelineDefinition,
    user: CurrentUser,
    parameters: dict | None = None,
) -> Execution:
    if not pipeline.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pipeline is inactive and cannot be run",
        )
    now = datetime.now(timezone.utc)
    execution = Execution(
        target_type="pipeline",
        pipeline_id=pipeline.id,
        target_name=pipeline.name,
        status="queued",
        engine="pipeline",
        parameters=parameters or {},
        triggered_by=user.email,
        queued_at=now,
    )
    db.add(execution)
    db.flush()
    record_audit(
        db,
        action="ingest.execution.enqueued",
        user=user,
        entity_type="execution",
        entity_id=execution.id,
        detail={"target_type": "pipeline", "pipeline_id": pipeline.id},
    )
    return execution


def cancel_execution(db: Session, *, execution: Execution, user: CurrentUser) -> Execution:
    if execution.status not in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Execution in status '{execution.status}' cannot be cancelled",
        )
    if execution.status == "queued":
        # Not started yet — cancel immediately so the worker never claims it.
        execution.status = "cancelled"
        execution.finished_at = datetime.now(timezone.utc)
        execution.final_message = f"Cancelled by {user.email}"
    else:
        # Running — request cooperative cancellation; the worker stops the process and
        # finalizes the status as 'cancelled' on its next heartbeat.
        execution.cancel_requested = True
        execution.final_message = f"Cancelamento solicitado por {user.email}"
    record_audit(
        db,
        action="ingest.execution.cancelled",
        user=user,
        entity_type="execution",
        entity_id=execution.id,
        detail={"requested_while": execution.status},
    )
    return execution


def enqueue_retry(db: Session, execution: Execution) -> Execution | None:
    """Enqueue a retry of a failed JOB execution if attempts remain (job.retry_count).

    Returns the new queued Execution, or None if no retry applies. Called from the worker.
    """
    if execution.target_type != "job" or not execution.job_id:
        return None
    job = db.get(JobDefinition, execution.job_id)
    if not job or not job.is_active:
        return None
    retries = int(job.retry_count or 0)
    if retries <= 0 or int(execution.attempt or 1) > retries:
        return None
    retry = create_job_execution(
        db,
        job=job,
        triggered_by=execution.triggered_by,
        trigger_type="retry",
        schedule_id=execution.schedule_id,
        parameters=execution.parameters or {},
        attempt=int(execution.attempt or 1) + 1,
    )
    return retry


def _stringify(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
