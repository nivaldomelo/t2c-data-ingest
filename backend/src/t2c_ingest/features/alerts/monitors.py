"""Silent-failure monitors: detect conditions that would otherwise go unnoticed and alert.

Cross-process coverage:
- the WORKER records a heartbeat each tick and detects overdue schedules (catches a stuck/dead
  scheduler);
- the SCHEDULER detects a dead worker (no recent worker heartbeat).
So each process watches the other's domain. Both down at once needs external liveness (K8s).
All emits are best-effort and de-duplicated with a small in-memory cooldown.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.features.alerts.service import emit


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _schema() -> str:
    return settings.db_schema or "t2c_data_ingest"


def heartbeat_worker(db: Session, worker_id: str) -> None:
    try:
        db.execute(text(
            f'INSERT INTO "{_schema()}".worker_heartbeats (worker_id, last_seen) '
            f'VALUES (:w, now()) ON CONFLICT (worker_id) DO UPDATE SET last_seen = now()'
        ), {"w": worker_id})
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


_overdue_alerted: set[int] = set()


def check_schedule_overdue(db: Session) -> None:
    """Emit SCHEDULE_OVERDUE for active schedules whose next_run_at passed the grace window."""
    try:
        from t2c_ingest.models.schedule import JobSchedule

        grace = settings.schedule_overdue_grace_seconds
        cutoff = _now() - timedelta(seconds=grace)
        rows = db.scalars(
            select(JobSchedule).where(
                JobSchedule.active.is_(True),
                JobSchedule.next_run_at.is_not(None),
                JobSchedule.next_run_at < cutoff,
            )
        ).all()
        current = set()
        for s in rows:
            current.add(s.id)
            if s.id in _overdue_alerted:
                continue
            emit(db, event_type="SCHEDULE_OVERDUE", severity="warning",
                 title=f"Schedule atrasado: {getattr(s, 'name', None) or s.id}",
                 message=f"next_run_at {s.next_run_at} passou do limite (grace {grace}s).",
                 job_id=s.job_id)
            _overdue_alerted.add(s.id)
        db.commit()
        # forget schedules that recovered so a future lateness alerts again
        for sid in list(_overdue_alerted):
            if sid not in current:
                _overdue_alerted.discard(sid)
    except Exception:  # noqa: BLE001
        db.rollback()


_worker_down_alerted = False


def check_worker_down(db: Session) -> None:
    """Emit WORKER_DOWN when a previously-seen worker stops heartbeating."""
    global _worker_down_alerted
    try:
        last = db.execute(text(f'SELECT max(last_seen) FROM "{_schema()}".worker_heartbeats')).scalar()
        # Only alert about a worker that existed and went silent (avoids boot false-positive).
        down = last is not None and (_now() - last).total_seconds() > settings.worker_down_threshold_seconds
        if down and not _worker_down_alerted:
            emit(db, event_type="WORKER_DOWN", severity="critical", title="Worker indisponível",
                 message=f"Nenhum heartbeat de worker nos últimos {settings.worker_down_threshold_seconds}s.")
            db.commit()
            _worker_down_alerted = True
        elif not down and _worker_down_alerted:
            _worker_down_alerted = False
    except Exception:  # noqa: BLE001
        db.rollback()
