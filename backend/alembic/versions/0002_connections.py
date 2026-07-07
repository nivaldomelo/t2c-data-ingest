"""connections table + job_definitions.connection_id

Revision ID: 0002_connections
Revises: 0001_initial
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from t2c_ingest.core.config import settings

revision: str = "0002_connections"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("connection_type", sa.String(20), nullable=False),
        sa.Column("host", sa.String(255)),
        sa.Column("port", sa.Integer()),
        sa.Column("database_name", sa.String(255)),
        sa.Column("username", sa.String(255)),
        sa.Column("password_encrypted", sa.Text()),
        sa.Column("schema_name", sa.String(255)),
        sa.Column("extra_params", postgresql.JSONB()),
        sa.Column("ssl_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_test_status", sa.String(20), nullable=False, server_default="not_tested"),
        sa.Column("last_test_message", sa.Text()),
        sa.Column("last_tested_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_ingest_connections_name"),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_connections_type", "connections", ["connection_type"], schema=SCHEMA)
    op.create_index("ix_ingest_connections_status", "connections", ["last_test_status"], schema=SCHEMA)

    # Optional link from a job to a reusable connection (not enforced/used yet).
    op.add_column(
        "job_definitions",
        sa.Column("connection_id", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_ingest_job_definitions_connection",
        "job_definitions",
        "connections",
        ["connection_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_ingest_job_definitions_connection_id", "job_definitions", ["connection_id"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_index("ix_ingest_job_definitions_connection_id", table_name="job_definitions", schema=SCHEMA)
    op.drop_constraint("fk_ingest_job_definitions_connection", "job_definitions", schema=SCHEMA, type_="foreignkey")
    op.drop_column("job_definitions", "connection_id", schema=SCHEMA)
    op.drop_table("connections", schema=SCHEMA)
