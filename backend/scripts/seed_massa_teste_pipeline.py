"""Seed the example pipeline ``pipeline_massa_teste_postgres_to_mysql`` (idempotent).

Builds a DAG from the postgres_to_mysql_massa_teste_* jobs:
    clientes -> pedidos -> {itens_pedido, pagamentos -> eventos_status}

Run:  docker compose exec api python scripts/seed_massa_teste_pipeline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.features.pipelines.graph_service import save_graph  # noqa: E402
from t2c_ingest.models.job import JobDefinition  # noqa: E402
from t2c_ingest.models.pipeline import PipelineDefinition  # noqa: E402

PIPELINE = "pipeline_massa_teste_postgres_to_mysql"
JOB_BY_STEP = {
    "clientes": "postgres_to_mysql_massa_teste_clientes",
    "pedidos": "postgres_to_mysql_massa_teste_pedidos",
    "itens_pedido": "postgres_to_mysql_massa_teste_itens_pedido",
    "pagamentos": "postgres_to_mysql_massa_teste_pagamentos",
    "eventos_status": "postgres_to_mysql_massa_teste_eventos_status",
}
EDGES = [
    ("clientes", "pedidos"),
    ("pedidos", "itens_pedido"),
    ("pedidos", "pagamentos"),
    ("pagamentos", "eventos_status"),
]
POS = {
    "clientes": (80, 200), "pedidos": (360, 200), "itens_pedido": (640, 100),
    "pagamentos": (640, 300), "eventos_status": (920, 300),
}


def main() -> None:
    with SessionLocal() as db:
        jobs = {j.name: j for j in db.scalars(select(JobDefinition).where(JobDefinition.name.in_(JOB_BY_STEP.values()))).all()}
        missing = [n for n in JOB_BY_STEP.values() if n not in jobs]
        if missing:
            print("Faltam jobs (rode seed_postgres_to_mysql.py primeiro):", missing)
            return

        p = db.scalar(select(PipelineDefinition).where(PipelineDefinition.name == PIPELINE))
        if p is None:
            p = PipelineDefinition(name=PIPELINE, created_by="system")
            db.add(p)
        p.description = "Ingestão massa_teste PostgreSQL → MySQL em ordem (clientes → pedidos → itens/pagamentos → eventos)."
        p.group_name = "massa_teste"
        p.is_active = True
        db.flush()

        nodes = [
            {"step_key": step, "job_id": jobs[job].id, "label": step,
             "position": {"x": POS[step][0], "y": POS[step][1]}, "parameters": {}}
            for step, job in JOB_BY_STEP.items()
        ]
        edges = [{"source_step_key": s, "target_step_key": t, "dependency_type": "success"} for s, t in EDGES]
        save_graph(db, p, nodes, edges)
        db.commit()
        print(f"Pipeline '{PIPELINE}' pronto (id={p.id}) com {len(nodes)} steps e {len(edges)} dependências.")


if __name__ == "__main__":
    main()
