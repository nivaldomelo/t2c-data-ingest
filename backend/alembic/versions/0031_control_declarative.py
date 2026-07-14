"""controle: campos declarativos de ingestão (CTRL-1) + summaries na execução

Revision ID: 0031_ctrl
Revises: 0030_dest_tpl
Create Date: 2026-07-14

CTRL-1: o Controle de Ingestão passa a descrever a carga completa de forma declarativa
(origem/destino por conexão ou destination_id, formato/write_mode/partições, SLA/owner/
frequência), para o runner executar full/incremental sem argumentos hardcoded no job.
Aditivo e compatível — nada é removido.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0031_ctrl"
down_revision: Union[str, None] = "0030_dest_tpl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"
C = settings.controle_schema or "controle"
T = f'"{C}".t2c_data_controle_ingestao'

_COLS = [
    # conexões (destination_id já criado em 0029)
    "source_connection_id INTEGER NULL",
    "target_connection_id INTEGER NULL",
    # origem
    "source_database VARCHAR(150) NULL",
    "source_schema VARCHAR(150) NULL",
    "source_table VARCHAR(255) NULL",
    "source_query TEXT NULL",
    "source_path TEXT NULL",
    "source_file_format VARCHAR(50) NULL",
    # destino relacional
    "target_database VARCHAR(150) NULL",
    "target_schema VARCHAR(150) NULL",
    "target_table VARCHAR(255) NULL",
    "staging_schema VARCHAR(150) NULL",
    "staging_table VARCHAR(255) NULL",
    # destino S3
    "target_bucket VARCHAR(255) NULL",
    "target_prefix TEXT NULL",
    "target_path TEXT NULL",
    "target_layer VARCHAR(50) NULL",
    "file_format VARCHAR(50) NULL",
    "compression VARCHAR(50) NULL",
    "partition_columns JSONB NULL",
    # estratégia de escrita
    "write_mode VARCHAR(50) NULL",
    "upsert_strategy VARCHAR(50) NULL",
    "truncate_before_load BOOLEAN NOT NULL DEFAULT FALSE",
    # frequência / owner / SLA
    "expected_frequency VARCHAR(50) NULL",
    "expected_frequency_minutes INTEGER NULL",
    "owner_name VARCHAR(150) NULL",
    "owner_email VARCHAR(255) NULL",
    "sla_minutes INTEGER NULL",
    "criticality VARCHAR(30) NULL",
    # extras
    "extra_params JSONB NULL",
]

_INDEXES = [
    ("idx_controle_ingestao_source_connection", "source_connection_id"),
    ("idx_controle_ingestao_target_connection", "target_connection_id"),
    ("idx_controle_ingestao_destination", "destination_id"),
    ("idx_controle_ingestao_grupo", "grupo"),
    ("idx_controle_ingestao_ativo", "ativo"),
    ("idx_controle_ingestao_status", "status"),
    ("idx_controle_ingestao_target_layer", "target_layer"),
    ("idx_controle_ingestao_expected_frequency", "expected_frequency"),
]


def upgrade() -> None:
    for col in _COLS:
        op.execute(f"ALTER TABLE {T} ADD COLUMN IF NOT EXISTS {col}")
    for name, col in _INDEXES:
        op.execute(f'CREATE INDEX IF NOT EXISTS {name} ON {T}({col})')
    # Execução: rastreabilidade da carga controlada resolvida.
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS control_id INTEGER NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS source_connection_id INTEGER NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS target_connection_id INTEGER NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS source_summary JSONB NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS target_summary JSONB NULL')


def downgrade() -> None:
    for col in ("source_summary", "target_summary", "source_connection_id", "target_connection_id", "control_id"):
        op.execute(f'ALTER TABLE "{S}".executions DROP COLUMN IF EXISTS {col}')
    for name, _ in _INDEXES:
        op.execute(f'DROP INDEX IF EXISTS "{C}".{name}')
    for col in _COLS:
        cname = col.split()[0]
        op.execute(f"ALTER TABLE {T} DROP COLUMN IF EXISTS {cname}")
