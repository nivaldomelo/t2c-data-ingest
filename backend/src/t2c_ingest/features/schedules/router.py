from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.schedules.manager import apply_next_run, create_schedule, schedule_out
from t2c_ingest.features.schedules.service import CronError, is_valid_cron, preview_next_runs
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.schedule import JobSchedule, ScheduleRun
from t2c_ingest.schemas.schedule import (
    CronValidateRequest,
    CronValidateResponse,
    ScheduleCreate,
    ScheduleOut,
    ScheduleRunOut,
    ScheduleSummary,
    ScheduleUpdate,
)
from t2c_ingest.schemas.execution import ExecutionOut
from t2c_ingest.services.audit import record_audit
from t2c_ingest.services.execution_service import enqueue_job_execution

router = APIRouter(prefix="/job-schedules", tags=["schedules"])


def _get(db: Session, schedule_id: int) -> JobSchedule:
    sch = db.get(JobSchedule, schedule_id)
    if not sch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agendamento não encontrado")
    return sch


@router.post("/validate-cron", response_model=CronValidateResponse)
def validate_cron(
    payload: CronValidateRequest,
    _: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_READ)),
) -> CronValidateResponse:
    if not is_valid_cron(payload.cron_expression):
        return CronValidateResponse(valid=False, error="Expressão cron inválida.")
    try:
        runs = preview_next_runs(payload.cron_expression, payload.timezone, count=5)
    except CronError as exc:
        return CronValidateResponse(valid=False, error=str(exc))
    return CronValidateResponse(valid=True, next_runs=runs)


@router.get("/summary", response_model=ScheduleSummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_READ)),
) -> ScheduleSummary:
    total = db.scalar(select(func.count(JobSchedule.id))) or 0
    active = db.scalar(select(func.count(JobSchedule.id)).where(JobSchedule.active.is_(True))) or 0
    now = datetime.now(timezone.utc)
    end_of_day = now.replace(hour=23, minute=59, second=59)
    next_today = (
        db.scalar(
            select(func.count(JobSchedule.id)).where(
                JobSchedule.active.is_(True),
                JobSchedule.next_run_at.is_not(None),
                JobSchedule.next_run_at <= end_of_day,
            )
        )
        or 0
    )
    last_error = (
        db.scalar(select(func.count(JobSchedule.id)).where(JobSchedule.last_status == "failed")) or 0
    )
    return ScheduleSummary(
        total=total, active=active, inactive=total - active, next_runs_today=next_today, last_error=last_error
    )


@router.get("", response_model=PageOut[ScheduleOut])
def list_schedules(
    params: PageParams = Depends(),
    job_id: int | None = None,
    active: bool | None = None,
    schedule_type: str | None = None,
    last_status: str | None = None,
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_READ)),
) -> PageOut[ScheduleOut]:
    stmt = select(JobSchedule)
    count_stmt = select(func.count(JobSchedule.id))
    filters = []
    if job_id:
        filters.append(JobSchedule.job_id == job_id)
    if active is not None:
        filters.append(JobSchedule.active.is_(active))
    if schedule_type:
        filters.append(JobSchedule.schedule_type == schedule_type)
    if last_status:
        filters.append(JobSchedule.last_status == last_status)
    if q:
        filters.append(or_(JobSchedule.name.ilike(f"%{q.strip()}%")))
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(JobSchedule.name).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([schedule_out(db, r) for r in rows], total, params)


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule_endpoint(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_WRITE)),
) -> ScheduleOut:
    if not payload.job_id:
        raise HTTPException(status_code=422, detail="job_id é obrigatório.")
    job = db.get(JobDefinition, payload.job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado")
    if payload.cron_expression and not is_valid_cron(payload.cron_expression):
        raise HTTPException(status_code=422, detail="Expressão cron inválida.")
    sch = create_schedule(db, job_id=payload.job_id, payload=payload, user=user)
    db.commit()
    return schedule_out(db, _get(db, sch.id))


@router.get("/{schedule_id}", response_model=ScheduleOut)
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_READ)),
) -> ScheduleOut:
    return schedule_out(db, _get(db, schedule_id))


@router.put("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_WRITE)),
) -> ScheduleOut:
    sch = _get(db, schedule_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("cron_expression") and not is_valid_cron(data["cron_expression"]):
        raise HTTPException(status_code=422, detail="Expressão cron inválida.")
    for key, value in data.items():
        setattr(sch, key, value)
    sch.updated_by = user.email
    apply_next_run(sch)
    record_audit(db, action="JOB_SCHEDULE_UPDATED", user=user, entity_type="job_schedule", entity_id=sch.id)
    db.commit()
    return schedule_out(db, _get(db, schedule_id))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_DELETE)),
) -> None:
    sch = _get(db, schedule_id)
    record_audit(db, action="JOB_SCHEDULE_DELETED", user=user, entity_type="job_schedule", entity_id=sch.id)
    db.delete(sch)
    db.commit()


@router.post("/{schedule_id}/enable", response_model=ScheduleOut)
def enable_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_ENABLE)),
) -> ScheduleOut:
    sch = _get(db, schedule_id)
    sch.active = True
    sch.updated_by = user.email
    apply_next_run(sch)
    record_audit(db, action="JOB_SCHEDULE_ENABLED", user=user, entity_type="job_schedule", entity_id=sch.id)
    db.commit()
    return schedule_out(db, _get(db, schedule_id))


@router.post("/{schedule_id}/disable", response_model=ScheduleOut)
def disable_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_DISABLE)),
) -> ScheduleOut:
    sch = _get(db, schedule_id)
    sch.active = False
    sch.next_run_at = None
    sch.updated_by = user.email
    record_audit(db, action="JOB_SCHEDULE_DISABLED", user=user, entity_type="job_schedule", entity_id=sch.id)
    db.commit()
    return schedule_out(db, _get(db, schedule_id))


@router.get("/{schedule_id}/runs", response_model=PageOut[ScheduleRunOut])
def schedule_runs(
    schedule_id: int,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_READ)),
) -> PageOut[ScheduleRunOut]:
    _get(db, schedule_id)
    total = db.scalar(select(func.count(ScheduleRun.id)).where(ScheduleRun.schedule_id == schedule_id)) or 0
    rows = db.scalars(
        select(ScheduleRun)
        .where(ScheduleRun.schedule_id == schedule_id)
        .order_by(ScheduleRun.id.desc())
        .offset(params.offset)
        .limit(params.limit)
    ).all()
    return PageOut.build([ScheduleRunOut.model_validate(r) for r in rows], total, params)


@router.post("/{schedule_id}/run", response_model=ExecutionOut, status_code=status.HTTP_202_ACCEPTED)
def run_now(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_SCHEDULES_RUN)),
) -> ExecutionOut:
    sch = _get(db, schedule_id)
    job = db.get(JobDefinition, sch.job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job do agendamento não encontrado")
    execution = enqueue_job_execution(
        db, job=job, user=user, parameters=sch.parameters, trigger_type="schedule", schedule_id=sch.id
    )
    now = datetime.now(timezone.utc)
    db.add(
        ScheduleRun(
            schedule_id=sch.id, job_id=job.id, execution_id=execution.id,
            scheduled_for=now, triggered_at=now, status="triggered", message=f"Disparo manual por {user.email}",
        )
    )
    sch.last_run_at = now
    sch.last_status = "queued"
    record_audit(db, action="JOB_SCHEDULE_TRIGGERED", user=user, entity_type="job_schedule", entity_id=sch.id,
                 detail={"execution_id": execution.id, "manual": True})
    db.commit()
    db.refresh(execution)
    return ExecutionOut.model_validate(execution)
