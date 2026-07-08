"""controle schema + t2c_data_controle_ingestao + job_definitions.ingestion_control_id

Revision ID: 0006_ingestion_control
Revises: 0005_job_schedules
Create Date: 2026-07-07

Non-destructive: everything uses IF NOT EXISTS so an existing table/data is preserved.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0006_ingestion_control"
down_revision: Union[str, None] = "0005_job_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = settings.db_schema or "t2c_data_ingest"
CONTROLE = settings.controle_schema or "controle"


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{CONTROLE}"')
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{CONTROLE}".t2c_data_controle_ingestao (
            id serial4 NOT NULL,
            nome_tabela text NOT NULL,
            coluna_data varchar(100) NULL,
            coluna_ultima_alteracao varchar(100) NULL,
            grupo varchar(50) NULL,
            watermark_atual timestamp NULL,
            ultima_execucao timestamp NULL,
            status varchar(20) NULL,
            observacao text NULL,
            ativo bool NULL,
            criado_em timestamp NULL,
            atualizado_em timestamp NULL,
            tipo_tabela varchar(20) NULL,
            origem varchar(20) NULL,
            destino varchar(20) NULL,
            dados_sensiveis text NULL,
            tipo_ingestao text NULL,
            colunas_chave text NULL,
            origem_id text NULL,
            CONSTRAINT t2c_data_controle_ingestao_pkey PRIMARY KEY (id)
        )
        """
    )
    for name, cols in [
        ("nome_tabela", "nome_tabela"),
        ("grupo", "grupo"),
        ("status", "status"),
        ("ativo", "ativo"),
        ("tipo_ingestao", "tipo_ingestao"),
        ("origem_destino", "origem, destino"),
    ]:
        op.execute(
            f'CREATE INDEX IF NOT EXISTS idx_t2c_data_controle_ingestao_{name} '
            f'ON "{CONTROLE}".t2c_data_controle_ingestao ({cols})'
        )

    # Optional link from a job to a control record (cross-schema; plain int, no FK). Not required.
    op.execute(
        f'ALTER TABLE "{SCHEMA}".job_definitions '
        f"ADD COLUMN IF NOT EXISTS ingestion_control_id integer NULL"
    )


def downgrade() -> None:
    # Non-destructive: keep the control table/data. Only drop the optional job column.
    op.execute(f'ALTER TABLE "{SCHEMA}".job_definitions DROP COLUMN IF EXISTS ingestion_control_id')
