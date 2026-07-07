from __future__ import annotations

from sqlalchemy.orm import Session

from t2c_ingest.features.auth_bridge.deps import CurrentUser
from t2c_ingest.features.schedules.service import CronError, compute_next_run
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.schedule import JobSchedule
from t2c_ingest.schemas.schedule import ScheduleCreate, ScheduleOut
from t2c_ingest.services.audit import record_audit


def apply_next_run(schedule: JobSchedule) -> None:
    """(Re)compute ``next_run_at`` from the schedule's current fields.

    manual / inactive / missing-or-invalid cron => no next run. If the next run would be past
    ``end_at``, the schedule is finished (deactivated, no next run).
    """
    if not schedule.active or schedule.schedule_type == "manual" or not schedule.cron_expression:
        schedule.next_run_at = None
        return
    try:
        nxt = compute_next_run(
            schedule.cron_expression, schedule.timezone, start_at=schedule.start_at
        )
    except CronError:
        schedule.next_run_at = None
        return
    if schedule.end_at is not None and nxt > schedule.end_at.astimezone(nxt.tzinfo):
        schedule.next_run_at = None
        schedule.active = False
        return
    schedule.next_run_at = nxt


def schedule_out(db: Session, schedule: JobSchedule) -> ScheduleOut:
    out = ScheduleOut.model_validate(schedule)
    job = db.get(JobDefinition, schedule.job_id)
    out.job_name = job.name if job else None
    return out


def create_schedule(db: Session, *, job_id: int, payload: ScheduleCreate, user: CurrentUser) -> JobSchedule:
    data = payload.model_dump(exclude={"job_id"})
    schedule = JobSchedule(**data, job_id=job_id, created_by=user.email, updated_by=user.email)
    db.add(schedule)
    apply_next_run(schedule)
    db.flush()
    record_audit(
        db,
        action="JOB_SCHEDULE_CREATED",
        user=user,
        entity_type="job_schedule",
        entity_id=schedule.id,
        detail={"job_id": job_id, "schedule_type": schedule.schedule_type},
    )
    return schedule
