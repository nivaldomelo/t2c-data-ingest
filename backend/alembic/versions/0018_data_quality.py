"""data quality results (ingest) + operational lineage/metadata pushed to t2c_data

Revision ID: 0018_dq
Revises: 0017_alerts
Create Date: 2026-07-09

Additive/non-destructive. Writes a lineage table INTO the reference schema (t2c_data) so the base
product can build lineage from real ingest executions.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0018_dq"
down_revision: Union[str, None] = "0017_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"
R = settings.reference_schema or "t2c_data"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".dq_results (
            id SERIAL PRIMARY KEY,
            execution_id INTEGER NULL,
            job_id INTEGER NULL,
            job_name VARCHAR(200) NULL,
            table_name TEXT NULL,
            tipo_ingestao VARCHAR(30) NULL,
            records_read INTEGER NULL,
            records_written INTEGER NULL,
            watermark_before TEXT NULL,
            watermark_after TEXT NULL,
            checks JSONB NULL,
            overall VARCHAR(20) NOT NULL DEFAULT 'pass',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_dq_results_exec ON "{S}".dq_results (execution_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_dq_results_overall ON "{S}".dq_results (overall, id)')

    # Operational lineage/metadata written into the reference schema (t2c_data) for the base product.
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{R}".ingest_lineage (
            id SERIAL PRIMARY KEY,
            execution_id INTEGER NULL,
            job_id INTEGER NULL,
            job_name VARCHAR(200) NULL,
            pipeline_id INTEGER NULL,
            source_connection VARCHAR(150) NULL,
            source_type VARCHAR(30) NULL,
            target_connection VARCHAR(150) NULL,
            target_type VARCHAR(30) NULL,
            table_source TEXT NULL,
            table_target TEXT NULL,
            camada VARCHAR(30) NULL,
            records_read INTEGER NULL,
            records_written INTEGER NULL,
            tipo_ingestao VARCHAR(30) NULL,
            status VARCHAR(30) NULL,
            executed_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_t2cdata_ingest_lineage_job ON "{R}".ingest_lineage (job_id, id)')


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{R}".ingest_lineage')
    op.execute(f'DROP TABLE IF EXISTS "{S}".dq_results')
