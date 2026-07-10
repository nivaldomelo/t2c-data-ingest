"""Backfill / reprocessing service.

Creates a controlled reprocessing request and enqueues the underlying executions, reusing the
normal execution/pipeline machinery (trigger_type="backfill"). A worker tick rolls up the final
status. Watermark reset is optional and permission-gated (checked in the router).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.features.auth_bridge.deps import CurrentUser
from t2c_ingest.models.backfill import BackfillRun
from t2c_ingest.models.execution import Execution
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.services.audit import record_audit

_TERMINAL = {"success", "failed", "cancelled", "timeout", "skipped"}


class BackfillError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_watermark(value: str | None, period_start: date | None) -> datetime | None:
    """Interpret the requested watermark reset value; empty => NULL (reprocess from scratch)."""
    raw = (value or "").strip()
    if not raw:
        return datetime(period_start.year, period_start.month, period_start.day) if period_start else None
    for parse in (lambda s: datetime.fromisoformat(s), lambda s: datetime.fromisoformat(s + "T00:00:00")):
        try:
            return parse(raw)
        except ValueError:
            continue
    raise BackfillError(422, f"Valor de watermark inválido: '{raw}'. Use ISO (AAAA-MM-DD ou AAAA-MM-DDTHH:MM:SS).")


def _base_params(bf: BackfillRun) -> dict:
    params: dict = {"backfill": True, "backfill_id": bf.id}
    if bf.period_start:
        params["period_start"] = bf.period_start.isoformat()
    if bf.period_end:
        params["period_end"] = bf.period_end.isoformat()
    if bf.reason:
        params["reason"] = bf.reason
    return params


def create_backfill(db: Session, user: CurrentUser, payload) -> BackfillRun:
    from t2c_ingest.features.ingestion_control.models import IngestionControl
    from t2c_ingest.features.pipelines.runner import start_pipeline_execution
    from t2c_ingest.models.pipeline import PipelineDefinition
    from t2c_ingest.services.execution_service import enqueue_job_execution

    kind = payload.kind
    bf = BackfillRun(
        kind=kind, job_id=payload.job_id, pipeline_id=payload.pipeline_id, from_step_id=payload.from_step_id,
        control_group=payload.control_group, table_name=payload.table_name,
        period_start=payload.period_start, period_end=payload.period_end,
        reset_watermark=payload.reset_watermark, watermark_value=payload.watermark_value,
        reason=payload.reason, status="queued", created_by=user.email, execution_ids=[],
    )
    db.add(bf)
    db.flush()
    record_audit(db, action="BACKFILL_REQUESTED", user=user, entity_type="backfill", entity_id=bf.id,
                 detail={"kind": kind})

    exec_ids: list[int] = []

    if kind == "job":
        job = db.get(JobDefinition, payload.job_id) if payload.job_id else None
        if not job or job.deleted_at is not None:
            raise BackfillError(404, "Job não encontrado ou excluído.")
        ex = enqueue_job_execution(db, job=job, user=user, parameters=_base_params(bf), trigger_type="backfill")
        db.flush()
        exec_ids = [ex.id]
        bf.total_targets = 1

    elif kind == "pipeline":
        pipeline = db.get(PipelineDefinition, payload.pipeline_id) if payload.pipeline_id else None
        if not pipeline:
            raise BackfillError(404, "Pipeline não encontrado.")
        pe = start_pipeline_execution(db, pipeline, triggered_by=user.email, trigger_type="backfill",
                                      from_step_id=payload.from_step_id)
        db.flush()
        bf.pipeline_execution_id = pe.id
        bf.total_targets = 1

    elif kind in ("control_group", "control_table"):
        stmt = select(IngestionControl)
        if kind == "control_group":
            if not payload.control_group:
                raise BackfillError(422, "Informe o grupo do controle de ingestão.")
            stmt = stmt.where(IngestionControl.grupo == payload.control_group)
        else:
            if not payload.table_name:
                raise BackfillError(422, "Informe a tabela do controle de ingestão.")
            stmt = stmt.where(IngestionControl.nome_tabela == payload.table_name)
        rows = list(db.scalars(stmt).all())
        if not rows:
            raise BackfillError(404, "Nenhum registro de controle encontrado para o alvo informado.")

        if payload.reset_watermark:
            new_wm = _parse_watermark(payload.watermark_value, payload.period_start)
            for r in rows:
                old = r.watermark_atual
                r.watermark_atual = new_wm
                record_audit(db, action="WATERMARK_RESET", user=user, entity_type="ingestion_control", entity_id=r.id,
                             detail={"tabela": r.nome_tabela, "old": str(old) if old else None,
                                     "new": str(new_wm) if new_wm else None, "backfill_id": bf.id})
            bf.watermarks_reset = len(rows)

        control_ids = [r.id for r in rows]
        jobs = list(db.scalars(
            select(JobDefinition).where(
                JobDefinition.ingestion_control_id.in_(control_ids),
                JobDefinition.deleted_at.is_(None),
            )
        ).all())
        for job in jobs:
            ex = enqueue_job_execution(db, job=job, user=user, parameters=_base_params(bf), trigger_type="backfill")
            db.flush()
            exec_ids.append(ex.id)
        bf.total_targets = len(jobs)
    else:
        raise BackfillError(422, f"Tipo de reprocessamento inválido: {kind}.")

    bf.execution_ids = exec_ids
    # Nothing to run (e.g. only a watermark reset) => already done.
    bf.status = "running" if (exec_ids or bf.pipeline_execution_id) else "success"
    if bf.status == "success":
        bf.finished_at = _now()
    record_audit(db, action="BACKFILL_STARTED", user=user, entity_type="backfill", entity_id=bf.id,
                 detail={"targets": bf.total_targets, "watermarks_reset": bf.watermarks_reset})
    db.commit()
    db.refresh(bf)
    return bf


def advance_backfills(db: Session) -> None:
    """Roll up backfill status once all spawned executions (or the pipeline run) finish."""
    from t2c_ingest.models.pipeline import PipelineExecution

    runs = db.scalars(select(BackfillRun).where(BackfillRun.status.in_(("queued", "running")))).all()
    for bf in runs:
        if bf.pipeline_execution_id:
            pe = db.get(PipelineExecution, bf.pipeline_execution_id)
            if pe and pe.status in ("success", "failed", "cancelled", "partial"):
                bf.status = "success" if pe.status == "success" else ("partial" if pe.status == "partial" else "failed")
                bf.succeeded = 1 if pe.status == "success" else 0
                bf.failed = 0 if pe.status == "success" else 1
                bf.finished_at = _now()
            continue
        ids = bf.execution_ids or []
        if not ids:
            continue
        execs = db.scalars(select(Execution).where(Execution.id.in_(ids))).all()
        if any(e.status not in _TERMINAL for e in execs):
            continue  # still running
        succeeded = sum(1 for e in execs if e.status == "success")
        failed = sum(1 for e in execs if e.status in ("failed", "timeout", "cancelled"))
        bf.succeeded = succeeded
        bf.failed = failed
        bf.status = "success" if failed == 0 else ("partial" if succeeded > 0 else "failed")
        bf.finished_at = _now()
    db.commit()
