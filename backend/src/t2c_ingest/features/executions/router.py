from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.executions.log_parser import parse_connections, parse_ingest_summary
from t2c_ingest.models.execution import Execution, ExecutionLog
from t2c_ingest.schemas.execution import (
    ExecutionConnectionInfo,
    ExecutionDetailOut,
    ExecutionLogOut,
    ExecutionOut,
    IngestSummaryOut,
)
from t2c_ingest.services.execution_service import cancel_execution

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=PageOut[ExecutionOut])
def list_executions(
    params: PageParams = Depends(),
    status_filter: str | None = Query(None, alias="status"),
    target_type: str | None = None,
    job_id: int | None = None,
    pipeline_id: int | None = None,
    engine: str | None = None,
    triggered_by: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> PageOut[ExecutionOut]:
    stmt = select(Execution)
    count_stmt = select(func.count(Execution.id))
    filters = []
    if status_filter:
        filters.append(Execution.status == status_filter)
    if target_type:
        filters.append(Execution.target_type == target_type)
    if job_id:
        filters.append(Execution.job_id == job_id)
    if pipeline_id:
        filters.append(Execution.pipeline_id == pipeline_id)
    if engine:
        filters.append(Execution.engine == engine)
    if triggered_by:
        filters.append(Execution.triggered_by == triggered_by)
    if date_from:
        filters.append(Execution.created_at >= date_from)
    if date_to:
        filters.append(Execution.created_at <= date_to)
    # Top-level executions only (hide per-step child executions from the main list).
    filters.append(Execution.parent_execution_id.is_(None))
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(Execution.id.desc()).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([ExecutionOut.model_validate(r) for r in rows], total, params)


@router.get("/{execution_id}", response_model=ExecutionDetailOut)
def get_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> ExecutionDetailOut:
    execution = db.scalar(
        select(Execution)
        .options(
            selectinload(Execution.logs),
            selectinload(Execution.artifacts),
            selectinload(Execution.runtime_parameters),
        )
        .where(Execution.id == execution_id)
    )
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    detail = ExecutionDetailOut.model_validate(execution)
    detail.execution_type = execution.target_type
    if execution.schedule_id:
        from t2c_ingest.models.schedule import JobSchedule, ScheduleRun

        sched = db.get(JobSchedule, execution.schedule_id)
        detail.schedule_name = sched.name if sched else None
        run = db.scalar(
            select(ScheduleRun)
            .where(ScheduleRun.execution_id == execution.id)
            .order_by(ScheduleRun.id.desc())
            .limit(1)
        )
        if run:
            detail.scheduled_for = run.scheduled_for
            detail.triggered_at = run.triggered_at
    _enrich_pipeline(db, execution, detail)
    _enrich_from_logs(execution, detail)
    return detail


def _enrich_pipeline(db: Session, execution: Execution, detail: ExecutionDetailOut) -> None:
    """Resolve pipeline / step context for a job execution created by a pipeline run."""
    from t2c_ingest.models.pipeline import PipelineDefinition, PipelineStep, PipelineStepExecution

    step_exec = db.scalar(
        select(PipelineStepExecution)
        .where(PipelineStepExecution.execution_id == execution.id)
        .order_by(PipelineStepExecution.id.desc())
        .limit(1)
    )
    pipeline_id = execution.pipeline_id or (step_exec.pipeline_id if step_exec else None)
    if step_exec:
        detail.pipeline_execution_id = step_exec.pipeline_execution_id
        step = db.get(PipelineStep, step_exec.step_id)
        if step:
            detail.step_name = step.label or step.name or step.step_key
            detail.step_order = step.order_index
    if pipeline_id:
        detail.pipeline_id = pipeline_id
        pipeline = db.get(PipelineDefinition, pipeline_id)
        detail.pipeline_name = pipeline.name if pipeline else None


def _enrich_from_logs(execution: Execution, detail: ExecutionDetailOut) -> None:
    """Parse structured metadata (connections / ingest summary) from the raw logs."""
    logs_text = "\n".join(log.message for log in execution.logs)
    if not logs_text.strip():
        return
    source, target = parse_connections(logs_text)
    if source:
        detail.source_connection = ExecutionConnectionInfo(**source)
    if target:
        detail.target_connection = ExecutionConnectionInfo(**target)
    summary = parse_ingest_summary(logs_text)
    if summary:
        detail.ingest_summary = IngestSummaryOut(**summary)
        detail.records_read = summary.get("lidos") if isinstance(summary.get("lidos"), int) else detail.records_read
        detail.records_written = summary.get("gravados") if isinstance(summary.get("gravados"), int) else detail.records_written


@router.get("/{execution_id}/logs", response_model=PageOut[ExecutionLogOut])
def get_execution_logs(
    execution_id: int,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_LOGS_READ)),
) -> PageOut[ExecutionLogOut]:
    if not db.get(Execution, execution_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    total = (
        db.scalar(select(func.count(ExecutionLog.id)).where(ExecutionLog.execution_id == execution_id))
        or 0
    )
    rows = db.scalars(
        select(ExecutionLog)
        .where(ExecutionLog.execution_id == execution_id)
        .order_by(ExecutionLog.seq, ExecutionLog.id)
        .offset(params.offset)
        .limit(params.limit)
    ).all()
    return PageOut.build([ExecutionLogOut.model_validate(r) for r in rows], total, params)


@router.post("/{execution_id}/cancel", response_model=ExecutionOut)
def cancel(
    execution_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_RUN)),
) -> ExecutionOut:
    execution = db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    cancel_execution(db, execution=execution, user=user)
    db.commit()
    db.refresh(execution)
    return ExecutionOut.model_validate(execution)
