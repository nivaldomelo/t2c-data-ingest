"""job_definitions: source/target connection, default_parameters, retry_count

Revision ID: 0003_job_detail_fields
Revises: 0002_connections
Create Date: 2026-07-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from t2c_ingest.core.config import settings

revision: str = "0003_job_detail_fields"
down_revision: Union[str, None] = "0002_connections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.add_column("job_definitions", sa.Column("source_connection_id", sa.Integer(), nullable=True), schema=SCHEMA)
    op.add_column("job_definitions", sa.Column("target_connection_id", sa.Integer(), nullable=True), schema=SCHEMA)
    op.add_column("job_definitions", sa.Column("default_parameters", postgresql.JSONB(), nullable=True), schema=SCHEMA)
    op.add_column(
        "job_definitions",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )
    for col in ("source_connection_id", "target_connection_id"):
        op.create_foreign_key(
            f"fk_ingest_job_definitions_{col}",
            "job_definitions",
            "connections",
            [col],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete="SET NULL",
        )
        op.create_index(f"ix_ingest_job_definitions_{col}", "job_definitions", [col], schema=SCHEMA)


def downgrade() -> None:
    for col in ("source_connection_id", "target_connection_id"):
        op.drop_index(f"ix_ingest_job_definitions_{col}", table_name="job_definitions", schema=SCHEMA)
        op.drop_constraint(f"fk_ingest_job_definitions_{col}", "job_definitions", schema=SCHEMA, type_="foreignkey")
    op.drop_column("job_definitions", "retry_count", schema=SCHEMA)
    op.drop_column("job_definitions", "default_parameters", schema=SCHEMA)
    op.drop_column("job_definitions", "target_connection_id", schema=SCHEMA)
    op.drop_column("job_definitions", "source_connection_id", schema=SCHEMA)
