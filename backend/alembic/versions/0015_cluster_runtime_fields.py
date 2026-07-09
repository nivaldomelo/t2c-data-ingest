"""clusters: expected workers, last check/validation, runtime image, environment

Revision ID: 0015_cluster_rt
Revises: 0014_job_indexes
Create Date: 2026-07-08

Additive/non-destructive.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0015_cluster_rt"
down_revision: Union[str, None] = "0014_job_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f'ALTER TABLE "{S}".clusters ADD COLUMN IF NOT EXISTS expected_workers INTEGER')
    op.execute(f'ALTER TABLE "{S}".clusters ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ')
    op.execute(f'ALTER TABLE "{S}".clusters ADD COLUMN IF NOT EXISTS last_validation_status VARCHAR(30)')
    op.execute(f'ALTER TABLE "{S}".clusters ADD COLUMN IF NOT EXISTS runtime_build_id INTEGER')
    op.execute(f'ALTER TABLE "{S}".clusters ADD COLUMN IF NOT EXISTS runtime_image VARCHAR(300)')
    op.execute(f'ALTER TABLE "{S}".clusters ADD COLUMN IF NOT EXISTS environment VARCHAR(30)')


def downgrade() -> None:
    for col in ("environment", "runtime_image", "runtime_build_id", "last_validation_status", "last_checked_at", "expected_workers"):
        op.execute(f'ALTER TABLE "{S}".clusters DROP COLUMN IF EXISTS {col}')
