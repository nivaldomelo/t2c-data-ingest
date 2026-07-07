"""job_code_versions history table

Revision ID: 0004_job_code_versions
Revises: 0003_job_detail_fields
Create Date: 2026-07-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from t2c_ingest.core.config import settings

revision: str = "0004_job_code_versions"
down_revision: Union[str, None] = "0003_job_detail_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.create_table(
        "job_code_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.job_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("script_path", sa.String(500), nullable=False),
        sa.Column("backup_path", sa.String(700)),
        sa.Column("content_hash_before", sa.String(64)),
        sa.Column("content_hash_after", sa.String(64)),
        sa.Column("changed_by", sa.String(255)),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("change_summary", sa.Text()),
        sa.Column("size_before_bytes", sa.Integer()),
        sa.Column("size_after_bytes", sa.Integer()),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_job_code_versions_job_id", "job_code_versions", ["job_id"], schema=SCHEMA)
    op.create_index("ix_ingest_job_code_versions_job_changed", "job_code_versions", ["job_id", "changed_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("job_code_versions", schema=SCHEMA)
