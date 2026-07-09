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
    db: Session, pipeline: PipelineDefinition, *, triggered_by: str, trigger_type: str = "manual"
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
    _release_ready_steps(db, pe)
    return pe


def _step_map(db: Session, pipeline_id: int) -> dict[int, PipelineStep]:
    steps = db.scalars(select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id)).all()
    return {s.id: s for s in steps}


def _deps(db: Session, pipeline_id: int) -> list[PipelineStepDependency]:
    return list(db.scalars(select(PipelineStepDependency).where(PipelineStepDependency.pipeline_id == pipeline_id)).all())


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
            up_states = [by_step_id.get(d.upstream_step_id) for d in ups]
            # An upstream that failed/skipped blocks a 'success' dependency.
            blocked = any(
                (u is None or u.status in {"failed", "skipped"})
                for d, u in zip(ups, up_states)
                if d.dependency_type in ("success", None)
            )
            if blocked:
                se.status = "skipped"
                se.message = "Upstream falhou ou foi ignorado."
                se.finished_at = _now()
                changed = True
                continue
            ready = all(u is not None and u.status == "success" for u in up_states)
            if ready:
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
