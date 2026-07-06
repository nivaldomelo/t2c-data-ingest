from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.execution import Execution
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.schemas.execution import ExecutionOut
from t2c_ingest.schemas.job import JobCreate, JobOut, JobRunRequest, JobUpdate
from t2c_ingest.services.audit import record_audit
from t2c_ingest.services.execution_service import enqueue_job_execution

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=PageOut[JobOut])
def list_jobs(
    params: PageParams = Depends(),
    type: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> PageOut[JobOut]:
    stmt = select(JobDefinition)
    count_stmt = select(func.count(JobDefinition.id))
    if type:
        stmt = stmt.where(JobDefinition.type == type)
        count_stmt = count_stmt.where(JobDefinition.type == type)
    if is_active is not None:
        stmt = stmt.where(JobDefinition.is_active == is_active)
        count_stmt = count_stmt.where(JobDefinition.is_active == is_active)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(JobDefinition.name).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([JobOut.model_validate(r) for r in rows], total, params)


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_WRITE)),
) -> JobOut:
    if db.scalar(select(JobDefinition).where(JobDefinition.name == payload.name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job name already exists")
    job = JobDefinition(**payload.model_dump(), created_by=user.email, updated_by=user.email)
    db.add(job)
    db.flush()
    record_audit(db, action="ingest.job.created", user=user, entity_type="job", entity_id=job.id)
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> JobOut:
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobOut.model_validate(job)


@router.patch("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_WRITE)),
) -> JobOut:
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, key, value)
    job.updated_by = user.email
    record_audit(db, action="ingest.job.updated", user=user, entity_type="job", entity_id=job.id)
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@router.post("/{job_id}/run", response_model=ExecutionOut, status_code=status.HTTP_202_ACCEPTED)
def run_job(
    job_id: int,
    payload: JobRunRequest | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_RUN)),
) -> ExecutionOut:
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    execution = enqueue_job_execution(
        db, job=job, user=user, parameters=(payload.parameters if payload else None)
    )
    db.commit()
    db.refresh(execution)
    return ExecutionOut.model_validate(execution)


@router.get("/{job_id}/executions", response_model=PageOut[ExecutionOut])
def job_executions(
    job_id: int,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> PageOut[ExecutionOut]:
    total = db.scalar(select(func.count(Execution.id)).where(Execution.job_id == job_id)) or 0
    rows = db.scalars(
        select(Execution)
        .where(Execution.job_id == job_id)
        .order_by(Execution.id.desc())
        .offset(params.offset)
        .limit(params.limit)
    ).all()
    return PageOut.build([ExecutionOut.model_validate(r) for r in rows], total, params)
