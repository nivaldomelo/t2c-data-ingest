"""job_definitions: soft-delete + archived code path

Revision ID: 0011_soft_delete
Revises: 0010_workspace
Create Date: 2026-07-08

Additive/non-destructive: adds soft-delete bookkeeping columns to job_definitions so a job can be
removed from the active listing while its code is archived (never hard-deleted).
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0011_soft_delete"
down_revision: Union[str, None] = "0010_workspace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f'ALTER TABLE "{S}".job_definitions ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ')
    op.execute(f'ALTER TABLE "{S}".job_definitions ADD COLUMN IF NOT EXISTS deleted_by VARCHAR(255)')
    op.execute(f'ALTER TABLE "{S}".job_definitions ADD COLUMN IF NOT EXISTS delete_reason TEXT')
    op.execute(f'ALTER TABLE "{S}".job_definitions ADD COLUMN IF NOT EXISTS archived_code_path VARCHAR(700)')
    # Speeds up the default "not deleted" listing filter.
    op.execute(
        f'CREATE INDEX IF NOT EXISTS ix_ingest_job_definitions_deleted_at '
        f'ON "{S}".job_definitions (deleted_at)'
    )


def downgrade() -> None:
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_ingest_job_definitions_deleted_at')
    op.execute(f'ALTER TABLE "{S}".job_definitions DROP COLUMN IF EXISTS archived_code_path')
    op.execute(f'ALTER TABLE "{S}".job_definitions DROP COLUMN IF EXISTS delete_reason')
    op.execute(f'ALTER TABLE "{S}".job_definitions DROP COLUMN IF EXISTS deleted_by')
    op.execute(f'ALTER TABLE "{S}".job_definitions DROP COLUMN IF EXISTS deleted_at')
