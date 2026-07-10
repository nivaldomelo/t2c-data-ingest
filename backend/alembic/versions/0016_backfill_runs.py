"""backfill_runs: reprocessing/backfill requests (job/pipeline/control group/table)

Revision ID: 0016_backfill
Revises: 0015_cluster_rt
Create Date: 2026-07-09

Additive/non-destructive.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0016_backfill"
down_revision: Union[str, None] = "0015_cluster_rt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".backfill_runs (
            id SERIAL PRIMARY KEY,
            kind VARCHAR(30) NOT NULL,
            job_id INTEGER NULL,
            pipeline_id INTEGER NULL,
            from_step_id INTEGER NULL,
            pipeline_execution_id INTEGER NULL,
            control_group VARCHAR(100) NULL,
            table_name TEXT NULL,
            period_start DATE NULL,
            period_end DATE NULL,
            reset_watermark BOOLEAN NOT NULL DEFAULT FALSE,
            watermark_value TEXT NULL,
            reason TEXT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            total_targets INTEGER NOT NULL DEFAULT 0,
            succeeded INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            execution_ids JSONB NULL,
            watermarks_reset INTEGER NOT NULL DEFAULT 0,
            message TEXT NULL,
            created_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_backfill_runs_status ON "{S}".backfill_runs (status, id)')


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{S}".backfill_runs')
