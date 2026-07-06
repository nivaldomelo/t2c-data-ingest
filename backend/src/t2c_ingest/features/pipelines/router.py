from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.models.pipeline import PipelineDefinition, PipelineStep
from t2c_ingest.schemas.execution import ExecutionOut
from t2c_ingest.schemas.pipeline import PipelineCreate, PipelineOut, PipelineUpdate
from t2c_ingest.services.audit import record_audit
from t2c_ingest.services.execution_service import enqueue_pipeline_execution

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


def _load(db: Session, pipeline_id: int) -> PipelineDefinition:
    pipeline = db.scalar(
        select(PipelineDefinition)
        .options(selectinload(PipelineDefinition.steps))
        .where(PipelineDefinition.id == pipeline_id)
    )
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    return pipeline


@router.get("", response_model=PageOut[PipelineOut])
def list_pipelines(
    params: PageParams = Depends(),
    layer: str | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> PageOut[PipelineOut]:
    stmt = select(PipelineDefinition).options(selectinload(PipelineDefinition.steps))
    count_stmt = select(func.count(PipelineDefinition.id))
    if layer:
        stmt = stmt.where(PipelineDefinition.layer == layer)
        count_stmt = count_stmt.where(PipelineDefinition.layer == layer)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(PipelineDefinition.name).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([PipelineOut.model_validate(r) for r in rows], total, params)


@router.post("", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_WRITE)),
) -> PipelineOut:
    if db.scalar(select(PipelineDefinition).where(PipelineDefinition.name == payload.name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pipeline name already exists")
    data = payload.model_dump(exclude={"steps"})
    pipeline = PipelineDefinition(**data, created_by=user.email)
    db.add(pipeline)
    db.flush()
    for step in payload.steps:
        db.add(PipelineStep(pipeline_id=pipeline.id, **step.model_dump()))
    record_audit(db, action="ingest.pipeline.created", user=user, entity_type="pipeline", entity_id=pipeline.id)
    db.commit()
    return PipelineOut.model_validate(_load(db, pipeline.id))


@router.get("/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_READ)),
) -> PipelineOut:
    return PipelineOut.model_validate(_load(db, pipeline_id))


@router.patch("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    pipeline_id: int,
    payload: PipelineUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_WRITE)),
) -> PipelineOut:
    pipeline = _load(db, pipeline_id)
    data = payload.model_dump(exclude_unset=True, exclude={"steps"})
    for key, value in data.items():
        setattr(pipeline, key, value)
    if payload.steps is not None:
        # replace all steps
        for step in list(pipeline.steps):
            db.delete(step)
        db.flush()
        for step in payload.steps:
            db.add(PipelineStep(pipeline_id=pipeline.id, **step.model_dump()))
    record_audit(db, action="ingest.pipeline.updated", user=user, entity_type="pipeline", entity_id=pipeline.id)
    db.commit()
    return PipelineOut.model_validate(_load(db, pipeline.id))


@router.post("/{pipeline_id}/run", response_model=ExecutionOut, status_code=status.HTTP_202_ACCEPTED)
def run_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_RUN)),
) -> ExecutionOut:
    pipeline = _load(db, pipeline_id)
    execution = enqueue_pipeline_execution(db, pipeline=pipeline, user=user)
    db.commit()
    db.refresh(execution)
    return ExecutionOut.model_validate(execution)
