"""T2C Data Ingest scheduler (separate process — NOT the web backend).

Every tick it claims due schedules (``active`` and ``next_run_at <= now``) with
``FOR UPDATE SKIP LOCKED`` so multiple schedulers never fire the same one, enqueues a job
execution (trigger_type=schedule, triggered_by=system_scheduler), records a schedule_run
(idempotent per schedule_id+scheduled_for), updates last_run/last_status and recomputes
``next_run_at`` FROM NOW — so a scheduler that was down does not backfill hundreds of runs;
it fires the due slot once and moves on to the next future slot.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from t2c_ingest.core.config import settings  # noqa: E402
from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.features.schedules.manager import apply_next_run  # noqa: E402
from t2c_ingest.models.job import JobDefinition  # noqa: E402
from t2c_ingest.models.schedule import JobSchedule, ScheduleRun  # noqa: E402
from t2c_ingest.models.audit import AuditEvent  # noqa: E402
from t2c_ingest.services.execution_service import create_job_execution  # noqa: E402

MAX_FIRES_PER_TICK = 50


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db, action: str, schedule: JobSchedule, detail: dict) -> None:
    try:
        db.add(
            AuditEvent(
                action=action,
                entity_type="job_schedule",
                entity_id=str(schedule.id),
                user_email="system_scheduler",
                detail=detail,
            )
        )
    except Exception:  # noqa: BLE001
        pass


def _fire_one() -> bool:
    """Claim and fire a single due schedule. Returns True if one was processed."""
    with SessionLocal() as db:
        now = _now()
        sch = db.scalar(
            select(JobSchedule)
            .where(
                JobSchedule.active.is_(True),
                JobSchedule.next_run_at.is_not(None),
                JobSchedule.next_run_at <= now,
            )
            .order_by(JobSchedule.next_run_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if sch is None:
            return False

        scheduled_for = sch.next_run_at

        # Respect end_at: finish the schedule instead of firing.
        if sch.end_at is not None and scheduled_for > sch.end_at:
            sch.active = False
            sch.next_run_at = None
            db.commit()
            return True

        job = db.get(JobDefinition, sch.job_id)
        run = ScheduleRun(
            schedule_id=sch.id,
            job_id=sch.job_id,
            scheduled_for=scheduled_for,
            triggered_at=now,
        )
        try:
            if not job or not job.is_active:
                run.status = "failed"
                run.message = "Job inexistente ou inativo."
                sch.last_status = "failed"
                _audit(db, "JOB_SCHEDULE_FAILED", sch, {"reason": run.message})
            else:
                execution = create_job_execution(
                    db,
                    job=job,
                    triggered_by="system_scheduler",
                    trigger_type="schedule",
                    schedule_id=sch.id,
                    parameters=sch.parameters,
                )
                run.execution_id = execution.id
                run.status = "triggered"
                run.message = f"Execução {execution.id} enfileirada."
                sch.last_status = "queued"
                delay = int((now - scheduled_for).total_seconds())
                if delay > 60:
                    run.message += f" (atraso de {delay}s)"
                _audit(db, "JOB_SCHEDULE_TRIGGERED", sch, {"execution_id": execution.id, "delay_seconds": delay})

            db.add(run)
            sch.last_run_at = now
            # Recompute the next run FROM NOW (no backfilling of missed slots).
            apply_next_run(sch)
            db.commit()
            print(f"[scheduler] schedule {sch.id} fired -> run status={run.status}")
            return True
        except IntegrityError:
            # Another process already recorded this exact slot — skip safely.
            db.rollback()
            return True
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            print(f"[scheduler] error firing schedule {sch.id}: {exc}")
            # Best-effort: advance next_run so we don't hot-loop on the same failing slot.
            try:
                with SessionLocal() as db2:
                    s2 = db2.get(JobSchedule, sch.id)
                    if s2:
                        s2.last_status = "failed"
                        apply_next_run(s2)
                        db2.commit()
            except Exception:  # noqa: BLE001
                pass
            return True


def main() -> None:
    from t2c_ingest.core.bootstrap import enforce_secure_config

    enforce_secure_config()  # refuse to run under insecure prod defaults
    poll = settings.scheduler_poll_interval_seconds
    print(f"[scheduler] started; tz={settings.scheduler_timezone}; polling every {poll}s")
    while True:
        fired = 0
        while fired < MAX_FIRES_PER_TICK and _fire_one():
            fired += 1
        time.sleep(poll)


if __name__ == "__main__":
    main()
