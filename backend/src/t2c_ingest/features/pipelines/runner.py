"""Pipeline orchestration (simple topological execution over worker ticks).

start_pipeline_execution() creates the pipeline execution + per-step rows (pending) and enqueues
the root steps as normal job executions (trigger_type=pipeline). advance_pipeline_executions()
is called by the worker each tick: it observes finished job executions, marks steps
success/failed/skipped, releases downstream steps whose upstreams all succeeded, and finalizes
the pipeline. Designed to support parallelism later (multiple ready steps enqueue together).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.models.execution import Execution
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.pipeline import (
    PipelineDefinition,
    PipelineExecution,
    PipelineStep,
    PipelineStepDependency,
    PipelineStepExecution,
)
from t2c_ingest.services.execution_service import create_job_execution

TERMINAL_JOB = {"success", "failed", "cancelled", "timeout", "skipped"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_pipeline_execution(
    db: Session, pipeline: PipelineDefinition, *, triggered_by: str, trigger_type: str = "manual",
    from_step_id: int | None = None,
) -> PipelineExecution:
    pe = PipelineExecution(
        pipeline_id=pipeline.id, status="running", trigger_type=trigger_type,
        triggered_by=triggered_by, started_at=_now(), parameters=pipeline.default_parameters or {},
    )
    db.add(pe)
    db.flush()
    for step in pipeline.steps:
        db.add(
            PipelineStepExecution(
                pipeline_execution_id=pe.id, pipeline_id=pipeline.id, step_id=step.id,
                job_id=step.job_id or 0, status="pending",
            )
        )
    db.flush()
    # Reprocess "from a step": mark steps NOT in {from_step} ∪ downstream as already-done so the
    # chosen step (and everything after it) runs while upstreams are reused.
    if from_step_id:
        keep = _downstream_closure(db, pipeline.id, from_step_id)
        for se in db.scalars(select(PipelineStepExecution).where(PipelineStepExecution.pipeline_execution_id == pe.id)).all():
            if se.step_id not in keep:
                se.status = "success"
                se.message = "Reaproveitado (reprocessamento a partir do step selecionado)."
                se.finished_at = _now()
        db.flush()
    _release_ready_steps(db, pe)
    return pe


def _downstream_closure(db: Session, pipeline_id: int, start_step_id: int) -> set[int]:
    """Return {start_step} plus every step reachable following downstream dependency edges."""
    adj: dict[int, list[int]] = {}
    for d in _deps(db, pipeline_id):
        adj.setdefault(d.upstream_step_id, []).append(d.downstream_step_id)
    seen = {start_step_id}
    stack = [start_step_id]
    while stack:
        for nxt in adj.get(stack.pop(), []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _step_map(db: Session, pipeline_id: int) -> dict[int, PipelineStep]:
    steps = db.scalars(select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id)).all()
    return {s.id: s for s in steps}


def _deps(db: Session, pipeline_id: int) -> list[PipelineStepDependency]:
    return list(db.scalars(select(PipelineStepDependency).where(PipelineStepDependency.pipeline_id == pipeline_id)).all())


_TERMINAL_STEP = {"success", "failed", "skipped", "timeout", "cancelled"}


def _dep_satisfied(dtype: str | None, up) -> bool:
    """Whether an upstream currently satisfies a dependency (requires it to be terminal)."""
    if up is None or up.status not in _TERMINAL_STEP:
        return False
    dtype = dtype or "success"
    if dtype == "success":
        return up.status == "success"
    if dtype == "failed":
        return up.status == "failed"
    return True  # finished / always: any terminal outcome satisfies


def _dep_impossible(dtype: str | None, up) -> bool:
    """Whether a dependency can NEVER be satisfied given the upstream's terminal state."""
    if up is None:
        return True
    if up.status not in _TERMINAL_STEP:
        return False  # still running/pending — may yet be satisfied
    dtype = dtype or "success"
    if dtype == "success":
        return up.status != "success"
    if dtype == "failed":
        return up.status != "failed"
    return False  # finished / always: never impossible once terminal


def _release_ready_steps(db: Session, pe: PipelineExecution) -> None:
    """Enqueue steps whose upstreams are all satisfied; skip those with a failed upstream."""
    step_execs = db.scalars(
        select(PipelineStepExecution).where(PipelineStepExecution.pipeline_execution_id == pe.id)
    ).all()
    by_step_id = {se.step_id: se for se in step_execs}
    deps = _deps(db, pe.pipeline_id)
    upstreams: dict[int, list[PipelineStepDependency]] = {}
    for d in deps:
        upstreams.setdefault(d.downstream_step_id, []).append(d)
    steps = _step_map(db, pe.pipeline_id)

    changed = True
    while changed:
        changed = False
        for se in step_execs:
            if se.status != "pending":
                continue
            ups = upstreams.get(se.step_id, [])
            pairs = [(d.dependency_type, by_step_id.get(d.upstream_step_id)) for d in ups]
            # Block (skip) if any dependency can NEVER be satisfied given the upstream's terminal state.
            if any(_dep_impossible(dtype, u) for dtype, u in pairs):
                se.status = "skipped"
                se.message = "Dependência não pode ser satisfeita (upstream)."
                se.finished_at = _now()
                changed = True
                continue
            if all(_dep_satisfied(dtype, u) for dtype, u in pairs):
                _enqueue_step(db, se, steps.get(se.step_id))
                changed = True
    db.flush()


def _enqueue_step(db: Session, se: PipelineStepExecution, step: PipelineStep | None) -> None:
    job = db.get(JobDefinition, step.job_id) if step and step.job_id else None
    if not job or not job.is_active:
        se.status = "failed"
        se.message = "Job inexistente ou inativo."
        se.finished_at = _now()
        return
    params = {**(step.parameters or {})}
    # Per-step timeout overrides the job's (honored by the worker). Carried in parameters to
    # avoid a schema change; the worker reads _timeout_seconds when present.
    if step and step.timeout_seconds:
        params["_timeout_seconds"] = int(step.timeout_seconds)
    execution = create_job_execution(
        db, job=job, triggered_by="pipeline", trigger_type="pipeline", parameters=params
    )
    se.execution_id = execution.id
    se.status = "running"
    se.started_at = _now()


def advance_pipeline_executions(db: Session) -> None:
    """Called by the worker each tick to progress running pipeline executions."""
    running = db.scalars(select(PipelineExecution).where(PipelineExecution.status == "running")).all()
    for pe in running:
        _advance_one(db, pe)
    if running:
        db.commit()


def _advance_one(db: Session, pe: PipelineExecution) -> None:
    step_execs = db.scalars(
        select(PipelineStepExecution).where(PipelineStepExecution.pipeline_execution_id == pe.id)
    ).all()

    # 1) reflect finished job executions onto step status.
    for se in step_execs:
        if se.status == "running" and se.execution_id:
            ex = db.get(Execution, se.execution_id)
            if ex and ex.status in TERMINAL_JOB:
                se.finished_at = _now()
                if se.started_at:
                    se.duration_seconds = int((se.finished_at - se.started_at).total_seconds())
                if ex.status == "success":
                    se.status = "success"
                    se.message = "Concluído com sucesso."
                else:
                    se.status = "failed"
                    se.message = f"Job terminou como {ex.status}."

    # 2) release newly-ready steps (and skip blocked ones).
    _release_ready_steps(db, pe)

    # 3) finalize when no step is pending/running.
    step_execs = db.scalars(
        select(PipelineStepExecution).where(PipelineStepExecution.pipeline_execution_id == pe.id)
    ).all()
    if any(se.status in ("pending", "running") for se in step_execs):
        return
    statuses = {se.status for se in step_execs}
    if statuses <= {"success"}:
        pe.status = "success"
        pe.message = "Todos os steps concluídos com sucesso."
    elif "failed" in statuses:
        pe.status = "failed" if "success" not in statuses and "skipped" not in statuses else "partial_success"
        pe.message = "Concluído com falhas." if pe.status != "failed" else "Pipeline falhou."
    else:
        pe.status = "partial_success"
        pe.message = "Concluído com steps ignorados."
    pe.finished_at = _now()
    if pe.started_at:
        pe.duration_seconds = int((pe.finished_at - pe.started_at).total_seconds())
    if pe.status in ("failed", "partial_success"):
        try:
            from t2c_ingest.features.alerts.service import emit
            from t2c_ingest.models.pipeline import PipelineDefinition

            pd = db.get(PipelineDefinition, pe.pipeline_id)
            emit(db, event_type="PIPELINE_FAILED",
                 severity="critical" if pe.status == "failed" else "warning",
                 title=f"Pipeline {'falhou' if pe.status == 'failed' else 'concluiu com falhas'}: {pd.name if pd else pe.pipeline_id}",
                 message=pe.message, pipeline_id=pe.pipeline_id, execution_id=pe.id)
        except Exception:  # noqa: BLE001
            pass
