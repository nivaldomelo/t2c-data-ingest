from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.execution import Execution, ExecutionLog
from t2c_ingest.schemas.execution import (
    ExecutionDetailOut,
    ExecutionLogOut,
    ExecutionOut,
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
    return ExecutionDetailOut.model_validate(execution)


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
