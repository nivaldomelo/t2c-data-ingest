"""execution reliability: attempt, lease/heartbeat, cancel flag + job max_active_runs

Revision ID: 0021_exec
Revises: 0020_idx
Create Date: 2026-07-09

Additive/non-destructive. Enables real retries, orphan-run recovery (lease), cooperative
cancellation and per-job concurrency limiting.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0021_exec"
down_revision: Union[str, None] = "0020_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS attempt INTEGER NOT NULL DEFAULT 1')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS worker_id VARCHAR(120) NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ NULL')
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS cancel_requested BOOLEAN NOT NULL DEFAULT FALSE')
    # Reaper query: running rows past their lease.
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_executions_lease ON "{S}".executions (status, lease_expires_at)')
    # 0 = unlimited (preserves current behavior).
    op.execute(f'ALTER TABLE "{S}".job_definitions ADD COLUMN IF NOT EXISTS max_active_runs INTEGER NOT NULL DEFAULT 0')


def downgrade() -> None:
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_ingest_executions_lease')
    for col in ("attempt", "heartbeat_at", "worker_id", "lease_expires_at", "cancel_requested"):
        op.execute(f'ALTER TABLE "{S}".executions DROP COLUMN IF EXISTS {col}')
    op.execute(f'ALTER TABLE "{S}".job_definitions DROP COLUMN IF EXISTS max_active_runs')
