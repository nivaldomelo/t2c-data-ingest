"""Outbox publisher: reliably deliver ingest events to t2c_data with retry + alerting.

Producers call enqueue() in their own transaction. The worker calls publish_pending() each tick
to deliver pending/failed rows; after too many failures a row goes 'dead' and a WORKER-visible
alert is raised, so a broken t2c_data push is never lost silently.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.models.outbox import IntegrationOutbox


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(db: Session, event_type: str, payload: dict) -> None:
    """Queue an integration event (must be JSON-serializable). Flush only — caller commits."""
    db.add(IntegrationOutbox(event_type=event_type, payload=payload, status="pending"))
    db.flush()


def _deliver(db: Session, row: IntegrationOutbox) -> None:
    """Perform the actual delivery for a row. Raises on failure."""
    if row.event_type == "lineage":
        r = settings.reference_schema or "t2c_data"
        db.execute(text(f"""
            INSERT INTO "{r}".ingest_lineage
              (execution_id, job_id, job_name, pipeline_id, source_connection, source_type,
               target_connection, target_type, table_source, table_target, camada,
               records_read, records_written, tipo_ingestao, status, executed_at)
            VALUES
              (:eid, :jid, :jname, :pid, :sconn, :stype, :tconn, :ttype, :tsource, :ttarget, :camada,
               :rr, :rw, :tipo, :status, :exec_at)
        """), row.payload)
        return
    raise RuntimeError(f"tipo de evento de integração desconhecido: {row.event_type}")


def publish_pending(db: Session, limit: int = 50) -> int:
    """Deliver pending/failed outbox rows. Returns how many were delivered successfully."""
    rows = db.scalars(
        select(IntegrationOutbox)
        .where(or_(IntegrationOutbox.status == "pending", IntegrationOutbox.status == "failed"))
        .where(IntegrationOutbox.attempts < settings.integration_max_attempts)
        .order_by(IntegrationOutbox.id)
        .limit(limit)
    ).all()
    if not rows:
        return 0
    sent = 0
    for row in rows:
        row_id, prev_attempts = row.id, row.attempts
        try:
            _deliver(db, row)
            row.attempts = prev_attempts + 1
            row.status = "sent"
            row.sent_at = _now()
            row.error = None
            db.commit()
            sent += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()  # discards the failed delivery
            new_attempts = prev_attempts + 1
            dead = new_attempts >= settings.integration_max_attempts
            db.execute(
                text(f'UPDATE "{settings.db_schema or "t2c_data_ingest"}".integration_outbox '
                     f'SET attempts = :n, status = :st, error = :err WHERE id = :id'),
                {"n": new_attempts, "st": "dead" if dead else "failed", "err": str(exc)[:500], "id": row_id},
            )
            db.commit()
            if dead:
                _alert_dead(db, row_id, new_attempts, str(exc))
    return sent


def _alert_dead(db: Session, row_id: int, attempts: int, error: str) -> None:
    try:
        from t2c_ingest.features.alerts.service import emit

        emit(db, event_type="INTEGRATION_FAILED", severity="critical",
             title="Falha ao enviar dados para o t2c_data",
             message=f"Evento de integração (outbox #{row_id}) falhou após {attempts} tentativas: {error}"[:1000])
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
