"""tags + job_tags

Revision ID: 0009_tags
Revises: 0008_pipeline_builder
Create Date: 2026-07-08

Additive/non-destructive.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0009_tags"
down_revision: Union[str, None] = "0008_pipeline_builder"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{S}".tags (
            id SERIAL PRIMARY KEY,
            name VARCHAR(80) NOT NULL,
            slug VARCHAR(100) NOT NULL,
            description TEXT NULL,
            color VARCHAR(20) NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by INTEGER NULL,
            updated_by INTEGER NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NULL
        )
        """
    )
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS uq_t2c_data_ingest_tags_slug ON "{S}".tags (slug)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_t2c_data_ingest_tags_name ON "{S}".tags (name)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_t2c_data_ingest_tags_active ON "{S}".tags (active)')

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{S}".job_tags (
            id SERIAL PRIMARY KEY,
            job_id INTEGER NOT NULL REFERENCES "{S}".job_definitions(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES "{S}".tags(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS uq_t2c_data_ingest_job_tags_job_tag ON "{S}".job_tags (job_id, tag_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_t2c_data_ingest_job_tags_job_id ON "{S}".job_tags (job_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_t2c_data_ingest_job_tags_tag_id ON "{S}".job_tags (tag_id)')


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{S}".job_tags')
    op.execute(f'DROP TABLE IF EXISTS "{S}".tags')
