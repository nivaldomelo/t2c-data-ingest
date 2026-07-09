"""job_definitions: indexes for the paginated Jobs grid (engine/type/active)

Revision ID: 0014_job_indexes
Revises: 0013_runtime
Create Date: 2026-07-08

Additive/non-destructive. name (unique) and deleted_at are already indexed.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0014_job_indexes"
down_revision: Union[str, None] = "0013_runtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_job_definitions_engine ON "{S}".job_definitions (engine)')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_job_definitions_type ON "{S}".job_definitions (type)')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_job_definitions_is_active ON "{S}".job_definitions (is_active)')


def downgrade() -> None:
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_ingest_job_definitions_is_active')
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_ingest_job_definitions_type')
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_ingest_job_definitions_engine')
