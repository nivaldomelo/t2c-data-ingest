"""pipeline builder: extend pipeline_definitions/steps + dependencies + pipeline executions

Revision ID: 0008_pipeline_builder
Revises: 0007_variables
Create Date: 2026-07-08

Additive/non-destructive: ADD COLUMN IF NOT EXISTS and CREATE TABLE IF NOT EXISTS.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0008_pipeline_builder"
down_revision: Union[str, None] = "0007_variables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    # Extend pipeline_definitions.
    op.execute(f'ALTER TABLE "{S}".pipeline_definitions ADD COLUMN IF NOT EXISTS group_name VARCHAR(80)')
    op.execute(f'ALTER TABLE "{S}".pipeline_definitions ADD COLUMN IF NOT EXISTS default_parameters JSONB')

    # Extend pipeline_steps (visual + run_if + active).
    for ddl in (
        "ADD COLUMN IF NOT EXISTS step_key VARCHAR(120)",
        "ADD COLUMN IF NOT EXISTS label VARCHAR(150)",
        "ADD COLUMN IF NOT EXISTS position_x NUMERIC(12,2)",
        "ADD COLUMN IF NOT EXISTS position_y NUMERIC(12,2)",
        "ADD COLUMN IF NOT EXISTS run_if VARCHAR(30) NOT NULL DEFAULT 'success'",
        "ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE",
    ):
        op.execute(f'ALTER TABLE "{S}".pipeline_steps {ddl}')

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{S}".pipeline_step_dependencies (
            id SERIAL PRIMARY KEY,
            pipeline_id INTEGER NOT NULL REFERENCES "{S}".pipeline_definitions(id) ON DELETE CASCADE,
            upstream_step_id INTEGER NOT NULL REFERENCES "{S}".pipeline_steps(id) ON DELETE CASCADE,
            downstream_step_id INTEGER NOT NULL REFERENCES "{S}".pipeline_steps(id) ON DELETE CASCADE,
            dependency_type VARCHAR(30) NOT NULL DEFAULT 'success',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_ingest_pipeline_dep UNIQUE (upstream_step_id, downstream_step_id)
        )
        """
    )
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_pipeline_dep_pipeline ON "{S}".pipeline_step_dependencies (pipeline_id)')

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{S}".pipeline_executions (
            id SERIAL PRIMARY KEY,
            pipeline_id INTEGER NOT NULL REFERENCES "{S}".pipeline_definitions(id) ON DELETE CASCADE,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            trigger_type VARCHAR(30) NOT NULL DEFAULT 'manual',
            triggered_by VARCHAR(120),
            started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, duration_seconds INTEGER,
            parameters JSONB, message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_pipeline_exec_pipeline ON "{S}".pipeline_executions (pipeline_id, created_at)')

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{S}".pipeline_step_executions (
            id SERIAL PRIMARY KEY,
            pipeline_execution_id INTEGER NOT NULL REFERENCES "{S}".pipeline_executions(id) ON DELETE CASCADE,
            pipeline_id INTEGER NOT NULL,
            step_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            execution_id INTEGER REFERENCES "{S}".executions(id) ON DELETE SET NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, duration_seconds INTEGER, message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_pipeline_step_exec_parent ON "{S}".pipeline_step_executions (pipeline_execution_id)')


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{S}".pipeline_step_executions')
    op.execute(f'DROP TABLE IF EXISTS "{S}".pipeline_executions')
    op.execute(f'DROP TABLE IF EXISTS "{S}".pipeline_step_dependencies')
    for col in ("step_key", "label", "position_x", "position_y", "run_if", "active"):
        op.execute(f'ALTER TABLE "{S}".pipeline_steps DROP COLUMN IF EXISTS {col}')
    op.execute(f'ALTER TABLE "{S}".pipeline_definitions DROP COLUMN IF EXISTS group_name')
    op.execute(f'ALTER TABLE "{S}".pipeline_definitions DROP COLUMN IF EXISTS default_parameters')
