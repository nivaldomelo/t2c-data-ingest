"""Seed controle.t2c_data_controle_ingestao with the massa_teste tables (idempotent).

Populates ingestion parameters for the sample OLTP tables so they can later be used by jobs
and pipelines. Skips a table if a control record with the same nome_tabela already exists —
safe to run multiple times. Run:

    docker compose exec api python scripts/seed_massa_teste_control.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.features.ingestion_control.models import IngestionControl  # noqa: E402

GRUPO = "massa_teste"

# Parametros por tabela. Regras:
# - tem updated_at -> INCREMENTAL por updated_at (coluna_ultima_alteracao); senao por data.
# - append-only (so created_at / dt_evento) -> INCREMENTAL por essa coluna, sem alteracao.
# - colunas_chave = chave de negocio (uuid) para merge/upsert.
RECORDS = [
    {
        "nome_tabela": "massa_teste.clientes",
        "tipo_tabela": "DIMENSAO",
        "tipo_ingestao": "INCREMENTAL",
        "coluna_data": "created_at",
        "coluna_ultima_alteracao": "updated_at",
        "colunas_chave": "cliente_uuid",
        "dados_sensiveis": "nome,email,documento",
        "observacao": "Cadastro de clientes (dimensão). Incremental por updated_at.",
    },
    {
        "nome_tabela": "massa_teste.pedidos",
        "tipo_tabela": "FATO",
        "tipo_ingestao": "INCREMENTAL",
        "coluna_data": "created_at",
        "coluna_ultima_alteracao": "updated_at",
        "colunas_chave": "pedido_uuid",
        "dados_sensiveis": None,
        "observacao": "Pedidos (fato). Incremental por updated_at.",
    },
    {
        "nome_tabela": "massa_teste.itens_pedido",
        "tipo_tabela": "FATO",
        "tipo_ingestao": "INCREMENTAL",
        "coluna_data": "created_at",
        "coluna_ultima_alteracao": None,
        "colunas_chave": "item_uuid",
        "dados_sensiveis": None,
        "observacao": "Itens de pedido (append-only). Incremental por created_at.",
    },
    {
        "nome_tabela": "massa_teste.pagamentos",
        "tipo_tabela": "FATO",
        "tipo_ingestao": "INCREMENTAL",
        "coluna_data": "created_at",
        "coluna_ultima_alteracao": "updated_at",
        "colunas_chave": "pagamento_uuid",
        "dados_sensiveis": None,
        "observacao": "Pagamentos (fato). Incremental por updated_at.",
    },
    {
        "nome_tabela": "massa_teste.eventos_status",
        "tipo_tabela": "LOG",
        "tipo_ingestao": "INCREMENTAL",
        "coluna_data": "dt_evento",
        "coluna_ultima_alteracao": None,
        "colunas_chave": "evento_uuid",
        "dados_sensiveis": None,
        "observacao": "Eventos de mudança de status (append-only). Incremental por dt_evento.",
    },
]

COMMON = {
    "grupo": GRUPO,
    "origem": "POSTGRES",
    "destino": "BRONZE",
    "status": "PENDENTE",
    "ativo": True,
    "origem_id": None,  # vincular a uma conexão cadastrada quando disponível
}


def main() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created, skipped = 0, 0
    with SessionLocal() as db:
        for rec in RECORDS:
            exists = db.scalar(
                select(IngestionControl).where(IngestionControl.nome_tabela == rec["nome_tabela"])
            )
            if exists:
                skipped += 1
                print(f"skip (já existe): {rec['nome_tabela']}")
                continue
            row = IngestionControl(**COMMON, **rec, criado_em=now, atualizado_em=now)
            db.add(row)
            created += 1
            print(f"criado: {rec['nome_tabela']} [{rec['tipo_ingestao']}]")
        db.commit()
    print(f"\nResumo: {created} criado(s), {skipped} já existente(s).")


if __name__ == "__main__":
    main()
