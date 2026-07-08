"""Seed control records (POSTGRES->MYSQL) + the 6 jobs for the massa_teste ingest (idempotent).

Run:  docker compose exec api python scripts/seed_postgres_to_mysql.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.features.ingestion_control.models import IngestionControl  # noqa: E402
from t2c_ingest.models.job import JobDefinition  # noqa: E402

SCRIPT = "/opt/t2c/spark/jobs/postgres_to_mysql/postgres_to_mysql_controlled_ingest.py"
GROUP = "massa_teste"
COMMON = dict(grupo=GROUP, origem="POSTGRES", destino="MYSQL", status="PENDENTE", ativo=True, origem_id="postgres_1")

CONTROL = [
    dict(nome_tabela="massa_teste.clientes", coluna_data="created_at", coluna_ultima_alteracao="updated_at",
         tipo_tabela="DIMENSAO", tipo_ingestao="INCREMENTAL", colunas_chave="id", dados_sensiveis="documento,email",
         observacao="Carga de clientes do PostgreSQL para MySQL"),
    dict(nome_tabela="massa_teste.pedidos", coluna_data="created_at", coluna_ultima_alteracao="updated_at",
         tipo_tabela="FATO", tipo_ingestao="INCREMENTAL", colunas_chave="id", dados_sensiveis=None,
         observacao="Carga de pedidos do PostgreSQL para MySQL"),
    dict(nome_tabela="massa_teste.itens_pedido", coluna_data="created_at", coluna_ultima_alteracao=None,
         tipo_tabela="FATO", tipo_ingestao="INCREMENTAL", colunas_chave="id", dados_sensiveis=None,
         observacao="Carga de itens de pedido do PostgreSQL para MySQL"),
    dict(nome_tabela="massa_teste.pagamentos", coluna_data="created_at", coluna_ultima_alteracao="updated_at",
         tipo_tabela="FATO", tipo_ingestao="INCREMENTAL", colunas_chave="id", dados_sensiveis=None,
         observacao="Carga de pagamentos do PostgreSQL para MySQL"),
    dict(nome_tabela="massa_teste.eventos_status", coluna_data="dt_evento", coluna_ultima_alteracao=None,
         tipo_tabela="LOG", tipo_ingestao="INCREMENTAL", colunas_chave="id", dados_sensiveis=None,
         observacao="Carga de eventos de status do PostgreSQL para MySQL"),
]

JOBS = [
    ("postgres_to_mysql_massa_teste_all", ["--control-group", GROUP, "--source-connection", "postgres_1", "--target-connection", "mysql_1"],
     "Ingestão controlada Postgres->MySQL de todas as tabelas do grupo massa_teste"),
    *[
        (f"postgres_to_mysql_massa_teste_{t}",
         ["--table-name", f"massa_teste.{t}", "--source-connection", "postgres_1", "--target-connection", "mysql_1"],
         f"Ingestão controlada Postgres->MySQL da tabela massa_teste.{t}")
        for t in ("clientes", "pedidos", "itens_pedido", "pagamentos", "eventos_status")
    ],
]


def main() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created_c = created_j = 0
    with SessionLocal() as db:
        # Control records (idempotent by nome_tabela + origem + destino + grupo).
        for rec in CONTROL:
            exists = db.scalar(
                select(IngestionControl).where(
                    IngestionControl.nome_tabela == rec["nome_tabela"],
                    IngestionControl.origem == "POSTGRES",
                    IngestionControl.destino == "MYSQL",
                    IngestionControl.grupo == GROUP,
                )
            )
            if exists:
                print(f"controle skip (existe): {rec['nome_tabela']}")
                continue
            db.add(IngestionControl(**COMMON, **rec, criado_em=now, atualizado_em=now))
            created_c += 1
            print(f"controle criado: {rec['nome_tabela']}")

        # Jobs (idempotent by name).
        for name, args, desc in JOBS:
            job = db.scalar(select(JobDefinition).where(JobDefinition.name == name))
            if job is None:
                job = JobDefinition(name=name, created_by="system")
                db.add(job)
                created_j += 1
            job.description = desc
            job.type = "spark_python"
            job.engine = "spark_cluster"
            job.script_path = SCRIPT
            job.arguments = args
            job.is_active = True
            job.updated_by = "system"
            print(f"job ok: {name}")
        db.commit()
    print(f"\nResumo: {created_c} controle criado(s), {created_j} job(s) criado(s).")


if __name__ == "__main__":
    main()
