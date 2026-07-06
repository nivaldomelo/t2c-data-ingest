from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
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


def enqueue_job_execution(
    db: Session,
    *,
    job: JobDefinition,
    user: CurrentUser,
    parameters: dict | None = None,
) -> Execution:
    """Register a queued execution for a job. The API never runs heavy work: the worker
    (Python) or the Spark cluster picks up the queued execution and updates it."""
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
        engine=_engine_for_job(job),
        cluster_id=job.cluster_id,
        parameters=parameters or {},
        triggered_by=user.email,
        queued_at=now,
    )
    db.add(execution)
    db.flush()
    for key, value in (parameters or {}).items():
        db.add(
            RuntimeParameter(execution_id=execution.id, key=str(key), value=_stringify(value))
        )
    record_audit(
        db,
        action="ingest.execution.enqueued",
        user=user,
        entity_type="execution",
        entity_id=execution.id,
        detail={"target_type": "job", "job_id": job.id, "engine": execution.engine},
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
    execution.status = "cancelled"
    execution.finished_at = datetime.now(timezone.utc)
    execution.final_message = f"Cancelled by {user.email}"
    record_audit(
        db,
        action="ingest.execution.cancelled",
        user=user,
        entity_type="execution",
        entity_id=execution.id,
    )
    return execution


def _stringify(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
