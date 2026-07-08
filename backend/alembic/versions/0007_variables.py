"""variables + job_variables

Revision ID: 0007_variables
Revises: 0006_ingestion_control
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0007_variables"
down_revision: Union[str, None] = "0006_ingestion_control"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{SCHEMA}".variables (
            id SERIAL PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            description TEXT NULL,
            value TEXT NULL,
            variable_type VARCHAR(30) NOT NULL DEFAULT 'string',
            scope VARCHAR(30) NOT NULL DEFAULT 'global',
            environment VARCHAR(30) NULL,
            is_secret BOOLEAN NOT NULL DEFAULT false,
            active BOOLEAN NOT NULL DEFAULT true,
            created_by INTEGER NULL,
            updated_by INTEGER NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NULL
        )
        """
    )
    op.execute(
        f'CREATE UNIQUE INDEX IF NOT EXISTS uq_t2c_data_ingest_variables_name_env_scope '
        f'ON "{SCHEMA}".variables (name, COALESCE(environment, \'\'), scope)'
    )
    for col in ("name", "scope", "environment", "active", "is_secret"):
        op.execute(
            f'CREATE INDEX IF NOT EXISTS idx_t2c_data_ingest_variables_{col} '
            f'ON "{SCHEMA}".variables ({col})'
        )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{SCHEMA}".job_variables (
            id SERIAL PRIMARY KEY,
            job_id INTEGER NOT NULL REFERENCES "{SCHEMA}".job_definitions(id) ON DELETE CASCADE,
            variable_id INTEGER NOT NULL REFERENCES "{SCHEMA}".variables(id) ON DELETE CASCADE,
            required BOOLEAN NOT NULL DEFAULT false,
            override_value TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_t2c_data_ingest_job_variables_job ON "{SCHEMA}".job_variables (job_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_t2c_data_ingest_job_variables_variable ON "{SCHEMA}".job_variables (variable_id)')


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{SCHEMA}".job_variables')
    op.execute(f'DROP TABLE IF EXISTS "{SCHEMA}".variables')
