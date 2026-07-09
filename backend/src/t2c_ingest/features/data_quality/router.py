from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.data_quality import DqResult
from t2c_ingest.schemas.data_quality import DqResultOut, DqSummary

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


@router.get("/summary", response_model=DqSummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_QUALITY_READ)),
) -> DqSummary:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    def c(overall: str | None = None) -> int:
        stmt = select(func.count(DqResult.id)).where(DqResult.created_at >= week_ago)
        if overall:
            stmt = stmt.where(DqResult.overall == overall)
        return db.scalar(stmt) or 0

    total = c()
    read = db.scalar(select(func.coalesce(func.sum(DqResult.records_read), 0)).where(DqResult.created_at >= week_ago)) or 0
    written = db.scalar(select(func.coalesce(func.sum(DqResult.records_written), 0)).where(DqResult.created_at >= week_ago)) or 0
    return DqSummary(
        total_7d=total, passed_7d=c("pass"), warn_7d=c("warn"), failed_7d=c("fail"),
        records_read_7d=int(read), records_written_7d=int(written),
    )


@router.get("/results", response_model=PageOut[DqResultOut])
def results(
    params: PageParams = Depends(),
    overall: str | None = None,
    job_id: int | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_QUALITY_READ)),
) -> PageOut[DqResultOut]:
    stmt = select(DqResult)
    count_stmt = select(func.count(DqResult.id))
    if overall:
        stmt = stmt.where(DqResult.overall == overall)
        count_stmt = count_stmt.where(DqResult.overall == overall)
    if job_id:
        stmt = stmt.where(DqResult.job_id == job_id)
        count_stmt = count_stmt.where(DqResult.job_id == job_id)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(DqResult.id.desc()).offset(params.offset).limit(params.limit)).all()
    return PageOut.build([DqResultOut.model_validate(r) for r in rows], total, params)
