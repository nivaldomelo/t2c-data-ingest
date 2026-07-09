from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.pipelines.graph_service import load_graph, save_graph, validate_graph
from t2c_ingest.features.pipelines.runner import start_pipeline_execution
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.execution import ExecutionLog
from t2c_ingest.models.pipeline import (
    PipelineDefinition,
    PipelineExecution,
    PipelineStep,
    PipelineStepDependency,
    PipelineStepExecution,
)
from t2c_ingest.schemas.pipeline import (
    GraphPayload,
    GraphStatus,
    GraphStatusEdge,
    GraphStatusNode,
    PipelineCreate,
    PipelineDetailOut,
    PipelineExecutionDetailOut,
    PipelineExecutionOut,
    PipelineOut,
    PipelineStepExecutionOut,
    PipelineUpdate,
    StepLogLine,
    StepLogs,
    TimelineEvent,
    ValidationResult,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/pipelines", tags=["pipelines"])
pe_router = APIRouter(prefix="/pipeline-executions", tags=["pipelines"])


def _load(db: Session, pipeline_id: int) -> PipelineDefinition:
    p = db.scalar(
        select(PipelineDefinition).options(selectinload(PipelineDefinition.steps)).where(PipelineDefinition.id == pipeline_id)
    )
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline não encontrado")
    return p


def _jobs_by_id(db: Session, ids: list[int]) -> dict[int, JobDefinition]:
    if not ids:
        return {}
    rows = db.scalars(select(JobDefinition).where(JobDefinition.id.in_(ids))).all()
    return {j.id: j for j in rows}


def _out(db: Session, p: PipelineDefinition) -> PipelineOut:
    out = PipelineOut.model_validate(p)
    out.steps_count = len(p.steps)
    return out


@router.get("", response_model=PageOut[PipelineOut])
def list_pipelines(
    params: PageParams = Depends(),
    group_name: str | None = None,
    layer: str | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> PageOut[PipelineOut]:
    stmt = select(PipelineDefinition).options(selectinload(PipelineDefinition.steps))
    count_stmt = select(func.count(PipelineDefinition.id))
    for cond in [c for c in [
        (PipelineDefinition.group_name == group_name) if group_name else None,
        (PipelineDefinition.layer == layer) if layer else None,
    ] if c is not None]:
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(PipelineDefinition.name).offset(params.offset).limit(params.limit)).all()
    return PageOut.build([_out(db, r) for r in rows], total, params)


@router.post("", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_WRITE)),
) -> PipelineOut:
    if db.scalar(select(PipelineDefinition).where(PipelineDefinition.name == payload.name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um pipeline com esse nome")
    p = PipelineDefinition(**payload.model_dump(), created_by=user.email)
    db.add(p)
    db.flush()
    record_audit(db, action="PIPELINE_CREATED", user=user, entity_type="pipeline", entity_id=p.id)
    db.commit()
    return _out(db, _load(db, p.id))


@router.get("/{pipeline_id}", response_model=PipelineDetailOut)
def get_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> PipelineDetailOut:
    p = _load(db, pipeline_id)
    detail = PipelineDetailOut.model_validate(p)
    detail.steps_count = len(p.steps)
    detail.dependencies_count = db.scalar(
        select(func.count(PipelineStepDependency.id)).where(PipelineStepDependency.pipeline_id == p.id)
    ) or 0
    detail.executions_total = db.scalar(
        select(func.count(PipelineExecution.id)).where(PipelineExecution.pipeline_id == p.id)
    ) or 0
    last = db.scalar(
        select(PipelineExecution).where(PipelineExecution.pipeline_id == p.id).order_by(PipelineExecution.id.desc()).limit(1)
    )
    if last:
        detail.last_execution_id = last.id
        detail.last_status = last.status
        detail.last_finished_at = last.finished_at
    avg = db.scalar(
        select(func.avg(PipelineExecution.duration_seconds)).where(
            PipelineExecution.pipeline_id == p.id, PipelineExecution.status == "success"
        )
    )
    detail.avg_duration_seconds = float(avg) if avg is not None else None
    return detail


@router.put("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    pipeline_id: int,
    payload: PipelineUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_WRITE)),
) -> PipelineOut:
    p = _load(db, pipeline_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    record_audit(db, action="PIPELINE_UPDATED", user=user, entity_type="pipeline", entity_id=p.id)
    db.commit()
    return _out(db, _load(db, pipeline_id))


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_DELETE)),
) -> None:
    p = _load(db, pipeline_id)
    record_audit(db, action="PIPELINE_DELETED", user=user, entity_type="pipeline", entity_id=p.id)
    db.delete(p)
    db.commit()


@router.get("/{pipeline_id}/graph", response_model=GraphPayload)
def get_graph(
    pipeline_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> GraphPayload:
    return GraphPayload(**load_graph(db, _load(db, pipeline_id)))


@router.get("/{pipeline_id}/steps")
def list_steps(
    pipeline_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> list[dict]:
    """Lightweight step list (id + label + order) for the backfill "reprocess from step" selector."""
    _load(db, pipeline_id)
    steps = db.scalars(
        select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order_index)
    ).all()
    return [{"id": s.id, "label": s.label or s.name or s.step_key or f"step {s.order_index}",
             "order_index": s.order_index} for s in steps]


@router.put("/{pipeline_id}/graph", response_model=GraphPayload)
def put_graph(
    pipeline_id: int,
    payload: GraphPayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_BUILDER)),
) -> GraphPayload:
    p = _load(db, pipeline_id)
    nodes = [n.model_dump() for n in payload.nodes]
    edges = [e.model_dump() for e in payload.edges]
    result = validate_graph(nodes, edges, _jobs_by_id(db, [n["job_id"] for n in nodes]))
    if not result["valid"]:
        raise HTTPException(status_code=422, detail={"message": "Graph inválido", **result})
    save_graph(db, p, nodes, edges)
    record_audit(db, action="PIPELINE_GRAPH_UPDATED", user=user, entity_type="pipeline", entity_id=p.id,
                 detail={"nodes": len(nodes), "edges": len(edges)})
    db.commit()
    return GraphPayload(**load_graph(db, _load(db, pipeline_id)))


@router.post("/{pipeline_id}/validate", response_model=ValidationResult)
def validate_pipeline(
    pipeline_id: int,
    payload: GraphPayload | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> ValidationResult:
    p = _load(db, pipeline_id)
    graph = {"nodes": [n.model_dump() for n in payload.nodes], "edges": [e.model_dump() for e in payload.edges]} if payload else load_graph(db, p)
    result = validate_graph(graph["nodes"], graph["edges"], _jobs_by_id(db, [n["job_id"] for n in graph["nodes"]]))
    return ValidationResult(**result)


@router.post("/{pipeline_id}/run", response_model=PipelineExecutionOut, status_code=status.HTTP_202_ACCEPTED)
def run_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_RUN)),
) -> PipelineExecutionOut:
    p = _load(db, pipeline_id)
    if not p.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pipeline inativo")
    graph = load_graph(db, p)
    result = validate_graph(graph["nodes"], graph["edges"], _jobs_by_id(db, [n["job_id"] for n in graph["nodes"]]))
    if not result["valid"]:
        raise HTTPException(status_code=422, detail={"message": "Pipeline inválido, corrija antes de executar", **result})
    pe = start_pipeline_execution(db, p, triggered_by=user.email, trigger_type="manual")
    record_audit(db, action="PIPELINE_EXECUTION_STARTED", user=user, entity_type="pipeline_execution", entity_id=pe.id,
                 detail={"pipeline_id": p.id})
    db.commit()
    db.refresh(pe)
    return PipelineExecutionOut.model_validate(pe)


@router.get("/{pipeline_id}/executions", response_model=PageOut[PipelineExecutionOut])
def pipeline_executions(
    pipeline_id: int,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> PageOut[PipelineExecutionOut]:
    _load(db, pipeline_id)
    total = db.scalar(select(func.count(PipelineExecution.id)).where(PipelineExecution.pipeline_id == pipeline_id)) or 0
    rows = db.scalars(
        select(PipelineExecution).where(PipelineExecution.pipeline_id == pipeline_id)
        .order_by(PipelineExecution.id.desc()).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([PipelineExecutionOut.model_validate(r) for r in rows], total, params)


@pe_router.get("/{execution_id}", response_model=PipelineExecutionDetailOut)
def pipeline_execution_detail(
    execution_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> PipelineExecutionDetailOut:
    pe = db.get(PipelineExecution, execution_id)
    if not pe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execução de pipeline não encontrada")
    detail = PipelineExecutionDetailOut.model_validate(pe)
    steps = db.scalars(
        select(PipelineStepExecution).where(PipelineStepExecution.pipeline_execution_id == pe.id).order_by(PipelineStepExecution.id)
    ).all()
    detail.steps = [PipelineStepExecutionOut.model_validate(s) for s in steps]
    return detail


@pe_router.get("/{execution_id}/steps", response_model=list[PipelineStepExecutionOut])
def pipeline_execution_steps(
    execution_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> list[PipelineStepExecutionOut]:
    steps = db.scalars(
        select(PipelineStepExecution).where(PipelineStepExecution.pipeline_execution_id == execution_id).order_by(PipelineStepExecution.id)
    ).all()
    return [PipelineStepExecutionOut.model_validate(s) for s in steps]


def _edge_status(src: str | None, tgt: str | None) -> str:
    if src == "success":
        return "success" if tgt in ("running", "success", "failed") else "released"
    if src in ("failed", "skipped"):
        return "blocked"
    return "waiting"


@pe_router.get("/{execution_id}/graph-status", response_model=GraphStatus)
def graph_status(
    execution_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> GraphStatus:
    pe = db.get(PipelineExecution, execution_id)
    if not pe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execução de pipeline não encontrada")
    step_execs = db.scalars(
        select(PipelineStepExecution).where(PipelineStepExecution.pipeline_execution_id == pe.id)
    ).all()
    status_by_step = {se.step_id: se.status for se in step_execs}
    step_keys = {s.id: s.step_key for s in db.scalars(select(PipelineStep).where(PipelineStep.pipeline_id == pe.pipeline_id)).all()}
    nodes = [
        GraphStatusNode(
            step_id=se.step_id, step_key=step_keys.get(se.step_id), job_id=se.job_id, status=se.status,
            started_at=se.started_at, finished_at=se.finished_at, duration_seconds=se.duration_seconds, message=se.message,
        )
        for se in step_execs
    ]
    deps = db.scalars(select(PipelineStepDependency).where(PipelineStepDependency.pipeline_id == pe.pipeline_id)).all()
    edges = [
        GraphStatusEdge(
            source_step_id=d.upstream_step_id, target_step_id=d.downstream_step_id,
            status=_edge_status(status_by_step.get(d.upstream_step_id), status_by_step.get(d.downstream_step_id)),
        )
        for d in deps
    ]
    return GraphStatus(
        pipeline_execution_id=pe.id, pipeline_id=pe.pipeline_id, status=pe.status,
        started_at=pe.started_at, finished_at=pe.finished_at, nodes=nodes, edges=edges,
    )


@pe_router.get("/{execution_id}/timeline", response_model=list[TimelineEvent])
def timeline(
    execution_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> list[TimelineEvent]:
    step_execs = db.scalars(
        select(PipelineStepExecution).where(PipelineStepExecution.pipeline_execution_id == execution_id)
    ).all()
    events: list[TimelineEvent] = []
    for se in step_execs:
        if se.started_at:
            events.append(TimelineEvent(time=se.started_at, step_id=se.step_id, job_id=se.job_id, event="iniciado", status="running"))
        if se.finished_at:
            ev = {"success": "sucesso", "failed": "erro", "skipped": "ignorado"}.get(se.status, se.status)
            events.append(TimelineEvent(time=se.finished_at, step_id=se.step_id, job_id=se.job_id, event=ev, status=se.status))
    events.sort(key=lambda e: e.time)
    return events


@pe_router.get("/{execution_id}/step/{step_execution_id}/logs", response_model=StepLogs)
def step_logs(
    execution_id: int,
    step_execution_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_PIPELINES_READ)),
) -> StepLogs:
    se = db.get(PipelineStepExecution, step_execution_id)
    if not se or se.pipeline_execution_id != execution_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step da execução não encontrado")
    lines: list[StepLogLine] = []
    if se.execution_id:
        rows = db.scalars(
            select(ExecutionLog).where(ExecutionLog.execution_id == se.execution_id)
            .order_by(ExecutionLog.seq.desc()).limit(max(1, min(limit, 500)))
        ).all()
        for r in reversed(rows):
            lines.append(StepLogLine(level=r.level, message=r.message[:4000]))
    return StepLogs(step_execution_id=se.id, execution_id=se.execution_id, status=se.status, message=se.message, lines=lines)
