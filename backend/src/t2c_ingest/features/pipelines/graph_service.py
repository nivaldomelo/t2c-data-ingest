from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.pipeline import PipelineDefinition, PipelineStep, PipelineStepDependency


def _topo_order(step_keys: list[str], edges: list[tuple[str, str]]) -> list[str] | None:
    """Kahn's algorithm. Returns topological order, or None if there is a cycle."""
    indeg = {k: 0 for k in step_keys}
    adj: dict[str, list[str]] = {k: [] for k in step_keys}
    for src, dst in edges:
        if src in adj and dst in indeg:
            adj[src].append(dst)
            indeg[dst] += 1
    queue = [k for k in step_keys if indeg[k] == 0]
    order: list[str] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return order if len(order) == len(step_keys) else None


def _find_cycle_path(step_keys: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Best-effort: return a node sequence forming a cycle (for a friendly message)."""
    adj: dict[str, list[str]] = {k: [] for k in step_keys}
    for src, dst in edges:
        if src in adj:
            adj[src].append(dst)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in step_keys}
    stack: list[str] = []

    def dfs(u: str) -> list[str] | None:
        color[u] = GRAY
        stack.append(u)
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                return stack[stack.index(v):] + [v]
            if color[v] == WHITE:
                r = dfs(v)
                if r:
                    return r
        color[u] = BLACK
        stack.pop()
        return None

    for k in step_keys:
        if color[k] == WHITE:
            r = dfs(k)
            if r:
                return r
    return []


def validate_graph(nodes: list[dict], edges: list[dict], jobs_by_id: dict[int, JobDefinition]) -> dict:
    """Return {'valid': bool, 'errors': [...], 'warnings': [...]}."""
    errors: list[str] = []
    warnings: list[str] = []

    if not nodes:
        errors.append("O pipeline precisa ter pelo menos um job.")
        return {"valid": False, "errors": errors, "warnings": warnings}

    keys = [n["step_key"] for n in nodes]
    if len(keys) != len(set(keys)):
        errors.append("Existem steps com step_key duplicado.")

    # Jobs exist / active.
    for n in nodes:
        job = jobs_by_id.get(n.get("job_id"))
        if not job:
            errors.append(f"Job do step '{n['step_key']}' não existe (job_id={n.get('job_id')}).")
        elif not job.is_active:
            warnings.append(f"O job do step '{n['step_key']}' está inativo.")

    # Edges reference existing nodes; no duplicates.
    edge_pairs = []
    seen_edges = set()
    keyset = set(keys)
    for e in edges:
        s, t = e.get("source_step_key"), e.get("target_step_key")
        if s not in keyset or t not in keyset:
            errors.append(f"Conexão inválida: {s} → {t} referencia step inexistente.")
            continue
        if s == t:
            errors.append(f"Conexão inválida: um step não pode depender de si mesmo ({s}).")
            continue
        pair = (s, t)
        if pair in seen_edges:
            errors.append(f"Conexão duplicada: {s} → {t}.")
            continue
        seen_edges.add(pair)
        edge_pairs.append(pair)

    # Cycle detection.
    if not errors:
        order = _topo_order(keys, edge_pairs)
        if order is None:
            cycle = _find_cycle_path(keys, edge_pairs)
            path = " → ".join(cycle) if cycle else "ciclo detectado"
            errors.append(f"O pipeline possui dependência circular: {path}.")

    # At least one root (no incoming edge).
    if not errors:
        with_incoming = {t for _, t in edge_pairs}
        roots = [k for k in keys if k not in with_incoming]
        if not roots:
            errors.append("O pipeline não possui nenhum job inicial (sem dependência anterior).")
        # Orphan nodes (no edges at all) when there is more than one node.
        if len(keys) > 1:
            connected = {s for s, _ in edge_pairs} | with_incoming
            orphans = [k for k in keys if k not in connected]
            for o in orphans:
                warnings.append(f"O step '{o}' está solto (sem conexões).")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def save_graph(db: Session, pipeline: PipelineDefinition, nodes: list[dict], edges: list[dict]) -> None:
    """Replace steps + dependencies from a nodes/edges payload (order_index = topological)."""
    # Drop existing steps (cascade removes dependencies).
    for st in list(pipeline.steps):
        db.delete(st)
    db.flush()

    keys = [n["step_key"] for n in nodes]
    edge_pairs = [(e["source_step_key"], e["target_step_key"]) for e in edges]
    order = _topo_order(keys, edge_pairs) or keys  # fall back to given order

    key_to_step: dict[str, PipelineStep] = {}
    for idx, key in enumerate(order):
        node = next(n for n in nodes if n["step_key"] == key)
        pos = node.get("position") or {}
        step = PipelineStep(
            pipeline_id=pipeline.id,
            order_index=idx,
            step_key=key,
            label=node.get("label"),
            name=node.get("label") or key,
            job_id=node.get("job_id"),
            position_x=pos.get("x"),
            position_y=pos.get("y"),
            run_if=node.get("run_if") or "success",
            parameters=node.get("parameters") or {},
            retry_count=int(node.get("retry_count") or 0),
            timeout_seconds=node.get("timeout_seconds"),
            active=node.get("active", True),
        )
        db.add(step)
        key_to_step[key] = step
    db.flush()

    for e in edges:
        up = key_to_step.get(e["source_step_key"])
        down = key_to_step.get(e["target_step_key"])
        if up and down:
            db.add(
                PipelineStepDependency(
                    pipeline_id=pipeline.id,
                    upstream_step_id=up.id,
                    downstream_step_id=down.id,
                    dependency_type=e.get("dependency_type") or "success",
                )
            )
    db.flush()


def load_graph(db: Session, pipeline: PipelineDefinition) -> dict:
    steps = list(pipeline.steps)
    by_id = {s.id: s for s in steps}
    deps = db.scalars(
        select(PipelineStepDependency).where(PipelineStepDependency.pipeline_id == pipeline.id)
    ).all()
    nodes = [
        {
            "step_key": s.step_key or f"step_{s.id}",
            "job_id": s.job_id,
            "label": s.label or s.name,
            "position": {"x": float(s.position_x) if s.position_x is not None else 0,
                         "y": float(s.position_y) if s.position_y is not None else 0},
            "run_if": s.run_if,
            "retry_count": s.retry_count,
            "timeout_seconds": s.timeout_seconds,
            "parameters": s.parameters or {},
            "active": s.active,
        }
        for s in steps
    ]
    edges = [
        {
            "source_step_key": by_id[d.upstream_step_id].step_key or f"step_{d.upstream_step_id}",
            "target_step_key": by_id[d.downstream_step_id].step_key or f"step_{d.downstream_step_id}",
            "dependency_type": d.dependency_type,
        }
        for d in deps
        if d.upstream_step_id in by_id and d.downstream_step_id in by_id
    ]
    return {"nodes": nodes, "edges": edges}
