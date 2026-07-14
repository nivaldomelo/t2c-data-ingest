"""destinations (destino configurável reutilizável) + destination_id em jobs/execuções/controle

Revision ID: 0029_dest
Revises: 0028_conn_cat
Create Date: 2026-07-13

DEST-1: o destino deixa de viver no código/args do job e passa a ser uma entidade declarativa,
reutilizável e governável, apontando para uma conexão. Aditivo e compatível: os campos antigos
de destino permanecem; destination_id é opcional.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0029_dest"
down_revision: Union[str, None] = "0028_conn_cat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"
CONTROLE = settings.controle_schema or "controle"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".destinations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            description TEXT NULL,
            destination_type VARCHAR(50) NOT NULL,
            connection_id INTEGER NOT NULL,
            target_schema VARCHAR(150) NULL,
            target_table VARCHAR(255) NULL,
            target_database VARCHAR(150) NULL,
            target_bucket VARCHAR(255) NULL,
            target_prefix TEXT NULL,
            target_path TEXT NULL,
            target_layer VARCHAR(50) NULL,
            file_format VARCHAR(50) NULL,
            write_mode VARCHAR(50) NOT NULL DEFAULT 'append',
            compression VARCHAR(50) NULL,
            partition_columns JSONB NULL,
            primary_key_columns JSONB NULL,
            staging_schema VARCHAR(150) NULL,
            staging_table VARCHAR(255) NULL,
            upsert_strategy VARCHAR(50) NULL,
            truncate_before_load BOOLEAN NOT NULL DEFAULT FALSE,
            options JSONB NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            last_test_status VARCHAR(20) NOT NULL DEFAULT 'not_tested',
            last_test_message TEXT NULL,
            last_tested_at TIMESTAMPTZ NULL,
            created_by VARCHAR(255) NULL,
            updated_by VARCHAR(255) NULL,
            deleted_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL,
            deleted_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_destinations_type ON "{S}".destinations(destination_type)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_destinations_connection ON "{S}".destinations(connection_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_destinations_active ON "{S}".destinations(active)')
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS uq_destinations_name_active ON "{S}".destinations(name) WHERE deleted_at IS NULL')

    # Referência declarativa de destino em jobs e execuções.
    op.execute(f'ALTER TABLE "{S}".job_definitions ADD COLUMN IF NOT EXISTS destination_id INTEGER NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS destination_id INTEGER NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS destination_type VARCHAR(50) NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS destination_summary JSONB NULL')

    # Controle de Ingestão referencia o destino configurável (schema controle).
    op.execute(f'ALTER TABLE "{CONTROLE}".t2c_data_controle_ingestao ADD COLUMN IF NOT EXISTS destination_id INTEGER NULL')


def downgrade() -> None:
    op.execute(f'ALTER TABLE "{CONTROLE}".t2c_data_controle_ingestao DROP COLUMN IF EXISTS destination_id')
    op.execute(f'ALTER TABLE "{S}".executions DROP COLUMN IF EXISTS destination_summary')
    op.execute(f'ALTER TABLE "{S}".executions DROP COLUMN IF EXISTS destination_type')
    op.execute(f'ALTER TABLE "{S}".executions DROP COLUMN IF EXISTS destination_id')
    op.execute(f'ALTER TABLE "{S}".job_definitions DROP COLUMN IF EXISTS destination_id')
    op.execute(f'DROP TABLE IF EXISTS "{S}".destinations')
