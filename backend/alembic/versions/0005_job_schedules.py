"""job_schedules + schedule_runs + executions.trigger_type/schedule_id

Revision ID: 0005_job_schedules
Revises: 0004_job_code_versions
Create Date: 2026-07-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from t2c_ingest.core.config import settings

revision: str = "0005_job_schedules"
down_revision: Union[str, None] = "0004_job_code_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    # executions: trigger provenance
    op.add_column(
        "executions",
        sa.Column("trigger_type", sa.String(20), nullable=False, server_default="manual"),
        schema=SCHEMA,
    )
    op.add_column("executions", sa.Column("schedule_id", sa.Integer(), nullable=True), schema=SCHEMA)
    op.create_index("ix_ingest_executions_schedule_id", "executions", ["schedule_id"], schema=SCHEMA)

    op.create_table(
        "job_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.job_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("schedule_type", sa.String(20), nullable=False, server_default="cron"),
        sa.Column("cron_expression", sa.String(120)),
        sa.Column("timezone", sa.String(60), nullable=False, server_default="America/Sao_Paulo"),
        sa.Column("start_at", sa.DateTime(timezone=True)),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("parameters", postgresql.JSONB()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(20)),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_job_schedules_job_id", "job_schedules", ["job_id"], schema=SCHEMA)
    op.create_index("ix_ingest_job_schedules_next_run_at", "job_schedules", ["next_run_at"], schema=SCHEMA)
    op.create_index("ix_ingest_job_schedules_active_next", "job_schedules", ["active", "next_run_at"], schema=SCHEMA)

    op.create_table(
        "schedule_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.job_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("execution_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.executions.id", ondelete="SET NULL")),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="triggered"),
        sa.Column("message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("schedule_id", "scheduled_for", name="uq_ingest_schedule_runs_slot"),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_schedule_runs_schedule_id", "schedule_runs", ["schedule_id"], schema=SCHEMA)
    op.create_index("ix_ingest_schedule_runs_job_id", "schedule_runs", ["job_id"], schema=SCHEMA)
    op.create_index("ix_ingest_schedule_runs_schedule", "schedule_runs", ["schedule_id", "triggered_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("schedule_runs", schema=SCHEMA)
    op.drop_table("job_schedules", schema=SCHEMA)
    op.drop_index("ix_ingest_executions_schedule_id", table_name="executions", schema=SCHEMA)
    op.drop_column("executions", "schedule_id", schema=SCHEMA)
    op.drop_column("executions", "trigger_type", schema=SCHEMA)
