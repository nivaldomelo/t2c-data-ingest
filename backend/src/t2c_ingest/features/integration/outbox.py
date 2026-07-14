"""Outbox publisher: entrega confiável de eventos operacionais ao t2c_data (ponto 16).

Padrão inalterado (aditivo): produtores chamam enqueue() na PRÓPRIA transação; o worker chama
publish_pending() a cada tick para entregar as linhas pendentes com retry + backoff exponencial e
dead-letter. Cada evento tem uma idempotency_key, então uma reentrega nunca duplica no t2c_data.

Estados: pending → processing → sent | failed → (backoff) pending → ... → dead.
Entrega: SEMPRE grava no sink genérico t2c_data.ingest_events (idempotente); lineage também
alimenta t2c_data.ingest_lineage (compatibilidade com o consumidor atual).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.features.integration import events as ev
from t2c_ingest.features.integration.events import Event
from t2c_ingest.models.outbox import IntegrationOutbox

# Backoff por número de falhas acumuladas: 1ª +1min, 2ª +5min, 3ª +15min, 4ª +1h, 5ª → dead.
_BACKOFF_MINUTES = (1, 5, 15, 60)
_DEFAULT_MAX_ATTEMPTS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _schema() -> str:
    return settings.db_schema or "t2c_data_ingest"


def _ref_schema() -> str:
    return settings.reference_schema or "t2c_data"


def _backoff(new_attempts: int) -> timedelta:
    idx = min(new_attempts - 1, len(_BACKOFF_MINUTES) - 1)
    return timedelta(minutes=_BACKOFF_MINUTES[idx])


# ─────────────────────────────── Enqueue ───────────────────────────────

def enqueue_event(db: Session, event: Event) -> None:
    """Enfileira um Event (idempotente). Flush apenas — quem chama faz o commit."""
    enqueue(
        db, event.event_type, event.payload,
        aggregate_type=event.aggregate_type, aggregate_id=event.aggregate_id,
        idempotency_key=event.idempotency_key, max_attempts=event.max_attempts,
    )


def enqueue(db: Session, event_type: str, payload: dict, *, aggregate_type: str | None = None,
            aggregate_id: str | None = None, idempotency_key: str | None = None,
            max_attempts: int = _DEFAULT_MAX_ATTEMPTS) -> None:
    """Insere uma linha na outbox. Com idempotency_key, um evento já enfileirado/entregue é
    ignorado (ON CONFLICT DO NOTHING sobre o índice único parcial)."""
    s = _schema()
    db.execute(
        text(f'''
            INSERT INTO "{s}".integration_outbox
                (event_type, aggregate_type, aggregate_id, payload, status, attempts,
                 max_attempts, idempotency_key, next_attempt_at, created_at)
            VALUES
                (:et, :at, :aid, CAST(:pl AS JSONB), 'pending', 0, :ma, :idem, now(), now())
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
        '''),
        {"et": event_type, "at": aggregate_type, "aid": aggregate_id,
         "pl": json.dumps(payload, default=str), "ma": max_attempts, "idem": idempotency_key},
    )
    db.flush()


# ─────────────────────────────── Publish ───────────────────────────────

def publish_pending(db: Session, limit: int = 50) -> int:
    """Entrega linhas prontas (pending/failed com next_attempt_at vencido). Retorna quantas
    foram entregues com sucesso. Retry com backoff; dead-letter + alerta ao esgotar tentativas."""
    now = _now()
    rows = db.scalars(
        select(IntegrationOutbox)
        .where(IntegrationOutbox.status.in_(("pending", "failed")))
        .where(IntegrationOutbox.attempts < IntegrationOutbox.max_attempts)
        .where(or_(IntegrationOutbox.next_attempt_at.is_(None),
                   IntegrationOutbox.next_attempt_at <= now))
        .order_by(IntegrationOutbox.id)
        .limit(limit)
    ).all()
    if not rows:
        return 0

    sent = 0
    for row in rows:
        rid, prev, maxa = row.id, row.attempts, row.max_attempts
        # Marca processing (rastreabilidade) antes de tentar entregar.
        row.status = "processing"
        row.last_attempt_at = now
        db.commit()
        try:
            _deliver(db, row)
            db.execute(
                text(f'UPDATE "{_schema()}".integration_outbox SET status = :st, attempts = :n, '
                     f'sent_at = now(), next_attempt_at = NULL, error = NULL, error_message = NULL, '
                     f'updated_at = now() WHERE id = :id'),
                {"st": "sent", "n": prev + 1, "id": rid},
            )
            db.commit()
            sent += 1
            _audit(db, "T2C_DATA_OUTBOX_EVENT_SENT", rid, row.event_type)
        except Exception as exc:  # noqa: BLE001
            db.rollback()  # descarta a entrega parcial
            new_attempts = prev + 1
            dead = new_attempts >= maxa
            nxt = None if dead else (_now() + _backoff(new_attempts))
            db.execute(
                text(f'UPDATE "{_schema()}".integration_outbox SET status = :st, attempts = :n, '
                     f'error = :err, error_message = :err, next_attempt_at = :nxt, '
                     f'dead_at = :dead_at, updated_at = now() WHERE id = :id'),
                {"st": "dead" if dead else "failed", "n": new_attempts, "err": str(exc)[:500],
                 "nxt": nxt, "dead_at": _now() if dead else None, "id": rid},
            )
            db.commit()
            _audit(db, "T2C_DATA_OUTBOX_EVENT_DEAD" if dead else "T2C_DATA_OUTBOX_EVENT_FAILED",
                   rid, row.event_type, {"attempts": new_attempts, "error": str(exc)[:300]})
            if dead:
                _alert_dead(db, rid, new_attempts, str(exc))
    return sent


def retry(db: Session, row_id: int) -> bool:
    """Reagenda uma linha (failed/dead) para entrega imediata. Retorna True se reagendou."""
    row = db.get(IntegrationOutbox, row_id)
    if not row or row.status == "sent":
        return False
    row.status = "pending"
    row.next_attempt_at = _now()
    row.dead_at = None
    if row.attempts >= row.max_attempts:
        row.max_attempts = row.attempts + _DEFAULT_MAX_ATTEMPTS  # dá mais fôlego a um dead reprocessado
    db.commit()
    _audit(db, "T2C_DATA_OUTBOX_EVENT_RETRIED", row_id, row.event_type)
    return True


def retry_dead(db: Session) -> int:
    """Reagenda TODAS as linhas dead. Retorna quantas foram reagendadas."""
    dead = db.scalars(select(IntegrationOutbox).where(IntegrationOutbox.status == "dead")).all()
    for row in dead:
        row.status = "pending"
        row.next_attempt_at = _now()
        row.dead_at = None
        row.max_attempts = row.attempts + _DEFAULT_MAX_ATTEMPTS
    if dead:
        db.commit()
        for row in dead:
            _audit(db, "T2C_DATA_OUTBOX_EVENT_RETRIED", row.id, row.event_type)
    return len(dead)


# ─────────────────────────────── Consultas (admin) ───────────────────────────────

def _row_to_dict(row: IntegrationOutbox, *, full: bool = False) -> dict:
    d = {
        "id": row.id, "event_type": row.event_type, "aggregate_type": row.aggregate_type,
        "aggregate_id": row.aggregate_id, "status": row.status, "attempts": row.attempts,
        "max_attempts": row.max_attempts, "idempotency_key": row.idempotency_key,
        "error": row.error_message or row.error,
        "created_at": row.created_at, "updated_at": row.updated_at,
        "next_attempt_at": row.next_attempt_at, "last_attempt_at": row.last_attempt_at,
        "sent_at": row.sent_at, "dead_at": row.dead_at,
    }
    if full:
        # Defesa em profundidade: o payload já é mascarado no enqueue; remascaramos ao expor.
        d["payload"] = ev.mask(row.payload or {})
    return d


def list_outbox(db: Session, *, status: str | None = None, event_type: str | None = None,
                aggregate_type: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    stmt = select(IntegrationOutbox)
    count_stmt = select(func.count(IntegrationOutbox.id))
    for col, val in ((IntegrationOutbox.status, status),
                     (IntegrationOutbox.event_type, event_type),
                     (IntegrationOutbox.aggregate_type, aggregate_type)):
        if val:
            stmt = stmt.where(col == val)
            count_stmt = count_stmt.where(col == val)
    total = db.scalar(count_stmt) or 0
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    rows = db.scalars(
        stmt.order_by(IntegrationOutbox.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [_row_to_dict(r) for r in rows]}


def get_outbox(db: Session, row_id: int) -> dict | None:
    row = db.get(IntegrationOutbox, row_id)
    return _row_to_dict(row, full=True) if row else None


def stats(db: Session) -> dict:
    by_status = dict(db.execute(
        select(IntegrationOutbox.status, func.count(IntegrationOutbox.id))
        .group_by(IntegrationOutbox.status)
    ).all())
    by_event = dict(db.execute(
        select(IntegrationOutbox.event_type, func.count(IntegrationOutbox.id))
        .group_by(IntegrationOutbox.event_type)
    ).all())
    last_sent = db.scalar(select(func.max(IntegrationOutbox.sent_at)))
    return {
        "by_status": {k: v for k, v in by_status.items()},
        "by_event_type": {k: v for k, v in by_event.items()},
        "pending": by_status.get("pending", 0) + by_status.get("processing", 0),
        "sent": by_status.get("sent", 0),
        "failed": by_status.get("failed", 0),
        "dead": by_status.get("dead", 0),
        "last_sent_at": last_sent,
    }


# ─────────────────────────────── Delivery ───────────────────────────────

def _deliver(db: Session, row: IntegrationOutbox) -> None:
    """Entrega de fato. Levanta exceção em falha (o publisher trata retry/dead)."""
    _sink_generic(db, row)  # sempre: sink genérico idempotente no t2c_data
    if row.event_type in ("lineage", ev.LINEAGE_EXECUTION_RECORDED):
        _deliver_lineage(db, row)


def _sink_generic(db: Session, row: IntegrationOutbox) -> None:
    """Grava o evento no sink genérico t2c_data.ingest_events (idempotente por idempotency_key)."""
    r = _ref_schema()
    payload = row.payload or {}
    occurred = payload.get("occurred_at") or payload.get("executed_at") or payload.get("opened_at") \
        or (payload.get("execution") or {}).get("finished_at")
    db.execute(
        text(f'''
            INSERT INTO "{r}".ingest_events
                (event_type, aggregate_type, aggregate_id, idempotency_key, source, payload, occurred_at)
            VALUES
                (:et, :at, :aid, :idem, 't2c_data_ingest', CAST(:pl AS JSONB), :occ)
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
        '''),
        {"et": row.event_type, "at": row.aggregate_type, "aid": row.aggregate_id,
         "idem": row.idempotency_key, "pl": json.dumps(payload, default=str), "occ": occurred},
    )


def _deliver_lineage(db: Session, row: IntegrationOutbox) -> None:
    """Alimenta t2c_data.ingest_lineage. Aceita o payload antigo (chaves curtas) e o novo
    (execution/job/source/target aninhados). Idempotente por execution_id."""
    r = _ref_schema()
    p = row.payload or {}
    if "execution" in p:  # payload novo (LINEAGE_EXECUTION_RECORDED)
        exe, job, pipe = p.get("execution") or {}, p.get("job") or {}, p.get("pipeline") or {}
        src, tgt, met = p.get("source") or {}, p.get("target") or {}, p.get("metrics") or {}
        args = {
            "eid": exe.get("id"), "jid": job.get("id"), "jname": job.get("name"),
            "pid": pipe.get("id"), "sconn": src.get("connection_name"), "stype": src.get("type"),
            "tconn": tgt.get("connection_name"), "ttype": tgt.get("type"),
            "tsource": src.get("table"), "ttarget": tgt.get("path") or tgt.get("database"),
            "camada": tgt.get("layer"), "rr": met.get("records_read"), "rw": met.get("records_written"),
            "tipo": exe.get("tipo_ingestao") or p.get("tipo"), "status": exe.get("status"),
            "exec_at": exe.get("finished_at") or exe.get("started_at"),
        }
    else:  # payload legado (event_type "lineage")
        args = {k: p.get(k) for k in ("eid", "jid", "jname", "pid", "sconn", "stype", "tconn",
                                       "ttype", "tsource", "ttarget", "camada", "rr", "rw",
                                       "tipo", "status", "exec_at")}
    db.execute(text(f'''
        INSERT INTO "{r}".ingest_lineage
          (execution_id, job_id, job_name, pipeline_id, source_connection, source_type,
           target_connection, target_type, table_source, table_target, camada,
           records_read, records_written, tipo_ingestao, status, executed_at)
        SELECT :eid, :jid, :jname, :pid, :sconn, :stype, :tconn, :ttype, :tsource, :ttarget, :camada,
               :rr, :rw, :tipo, :status, :exec_at
        WHERE :eid IS NULL OR NOT EXISTS (
            SELECT 1 FROM "{r}".ingest_lineage WHERE execution_id = :eid
        )
    '''), args)


# ─────────────────────────────── Auditoria + alerta ───────────────────────────────

def _audit(db: Session, action: str, row_id: int, event_type: str, detail: dict | None = None) -> None:
    """Auditoria interna dos eventos da outbox (best-effort, transação própria)."""
    try:
        from t2c_ingest.models.audit import AuditEvent
        d = {"event_type": event_type}
        if detail:
            d.update(detail)
        db.add(AuditEvent(action=action, entity_type="integration_outbox",
                          entity_id=str(row_id), detail=d))
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


def _alert_dead(db: Session, row_id: int, attempts: int, error: str) -> None:
    try:
        from t2c_ingest.features.alerts.service import emit

        emit(db, event_type="INTEGRATION_FAILED", severity="critical",
             title="Falha ao enviar dados para o t2c_data",
             message=f"Evento de integração (outbox #{row_id}) foi para dead-letter após "
                     f"{attempts} tentativas: {error}"[:1000])
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
