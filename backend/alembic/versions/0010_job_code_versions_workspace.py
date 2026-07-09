"""job_code_versions: action + file_path (workspace file ops)

Revision ID: 0010_workspace
Revises: 0009_tags
Create Date: 2026-07-08

Additive/non-destructive.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0010_workspace"
down_revision: Union[str, None] = "0009_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f"ALTER TABLE \"{S}\".job_code_versions ADD COLUMN IF NOT EXISTS action VARCHAR(30)")
    op.execute(f"ALTER TABLE \"{S}\".job_code_versions ADD COLUMN IF NOT EXISTS file_path VARCHAR(700)")


def downgrade() -> None:
    op.execute(f"ALTER TABLE \"{S}\".job_code_versions DROP COLUMN IF EXISTS file_path")
    op.execute(f"ALTER TABLE \"{S}\".job_code_versions DROP COLUMN IF EXISTS action")
