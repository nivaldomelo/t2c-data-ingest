from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.backfill import service
from t2c_ingest.models.backfill import BackfillRun
from t2c_ingest.models.execution import Execution
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.pipeline import PipelineDefinition
from t2c_ingest.schemas.backfill import (
    BackfillCreate,
    BackfillDetailOut,
    BackfillExecLite,
    BackfillOut,
)

router = APIRouter(prefix="/backfills", tags=["backfill"])


def _label(db: Session, bf: BackfillRun) -> str | None:
    if bf.kind == "job" and bf.job_id:
        j = db.get(JobDefinition, bf.job_id)
        return j.name if j else f"job #{bf.job_id}"
    if bf.kind == "pipeline" and bf.pipeline_id:
        p = db.get(PipelineDefinition, bf.pipeline_id)
        return p.name if p else f"pipeline #{bf.pipeline_id}"
    if bf.kind == "control_group":
        return f"grupo {bf.control_group}"
    if bf.kind == "control_table":
        return bf.table_name
    return None


def _out(db: Session, bf: BackfillRun) -> BackfillOut:
    o = BackfillOut.model_validate(bf)
    o.target_label = _label(db, bf)
    return o


@router.get("", response_model=PageOut[BackfillOut])
def list_backfills(
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> PageOut[BackfillOut]:
    total = db.scalar(select(func.count(BackfillRun.id))) or 0
    rows = db.scalars(select(BackfillRun).order_by(BackfillRun.id.desc()).offset(params.offset).limit(params.limit)).all()
    return PageOut.build([_out(db, b) for b in rows], total, params)


@router.post("", response_model=BackfillDetailOut, status_code=status.HTTP_201_CREATED)
def create_backfill(
    payload: BackfillCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_BACKFILL_RUN)),
) -> BackfillDetailOut:
    if payload.reset_watermark and not user.has(perms.INGEST_BACKFILL_WATERMARK):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Você não tem permissão para redefinir watermark.")
    try:
        bf = service.create_backfill(db, user, payload)
    except service.BackfillError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return _detail(db, bf)


@router.get("/{backfill_id}", response_model=BackfillDetailOut)
def get_backfill(
    backfill_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> BackfillDetailOut:
    bf = db.get(BackfillRun, backfill_id)
    if not bf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backfill não encontrado")
    return _detail(db, bf)


def _detail(db: Session, bf: BackfillRun) -> BackfillDetailOut:
    detail = BackfillDetailOut.model_validate(bf)
    detail.target_label = _label(db, bf)
    ids = bf.execution_ids or []
    if ids:
        execs = db.scalars(select(Execution).where(Execution.id.in_(ids)).order_by(Execution.id)).all()
        detail.executions = [
            BackfillExecLite(id=e.id, target_name=e.target_name, status=e.status,
                             started_at=e.started_at, finished_at=e.finished_at, duration_seconds=e.duration_seconds)
            for e in execs
        ]
    return detail
