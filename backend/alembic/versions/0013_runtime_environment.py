"""runtime environment: managed libraries manifest + image builds + cluster validations

Revision ID: 0013_runtime
Revises: 0012_libraries
Create Date: 2026-07-08

Additive/non-destructive.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0013_runtime"
down_revision: Union[str, None] = "0012_libraries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".runtime_libraries (
            id SERIAL PRIMARY KEY,
            package_name VARCHAR(200) NOT NULL,
            package_version VARCHAR(100) NULL,
            package_spec VARCHAR(300) NOT NULL,
            source VARCHAR(30) NOT NULL DEFAULT 'pypi',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            note TEXT NULL,
            created_by VARCHAR(255) NULL,
            updated_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(
        f'CREATE UNIQUE INDEX IF NOT EXISTS uq_ingest_runtime_libraries_name '
        f'ON "{S}".runtime_libraries (package_name)'
    )
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".runtime_builds (
            id SERIAL PRIMARY KEY,
            build_version VARCHAR(100) NOT NULL,
            image_name VARCHAR(300) NOT NULL,
            image_tag VARCHAR(150) NOT NULL,
            image_full_name VARCHAR(500) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            requirements_snapshot TEXT NULL,
            jobs_snapshot_path TEXT NULL,
            dockerfile_path TEXT NULL,
            context_path TEXT NULL,
            build_logs TEXT NULL,
            error_message TEXT NULL,
            started_at TIMESTAMPTZ NULL,
            finished_at TIMESTAMPTZ NULL,
            duration_seconds INTEGER NULL,
            created_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        f'CREATE INDEX IF NOT EXISTS ix_ingest_runtime_builds_status ON "{S}".runtime_builds (status, id)'
    )
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".runtime_validations (
            id SERIAL PRIMARY KEY,
            runtime_build_id INTEGER NULL,
            validation_type VARCHAR(50) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            worker_count_expected INTEGER NULL,
            worker_count_detected INTEGER NULL,
            libraries_checked JSONB NULL,
            workers_result JSONB NULL,
            logs TEXT NULL,
            error_message TEXT NULL,
            started_at TIMESTAMPTZ NULL,
            finished_at TIMESTAMPTZ NULL,
            created_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        f'CREATE INDEX IF NOT EXISTS ix_ingest_runtime_validations_status ON "{S}".runtime_validations (status, id)'
    )
    # A job may pin a specific runtime image (optional; NULL = active default).
    op.execute(f'ALTER TABLE "{S}".job_definitions ADD COLUMN IF NOT EXISTS runtime_build_id INTEGER NULL')


def downgrade() -> None:
    op.execute(f'ALTER TABLE "{S}".job_definitions DROP COLUMN IF EXISTS runtime_build_id')
    op.execute(f'DROP TABLE IF EXISTS "{S}".runtime_validations')
    op.execute(f'DROP TABLE IF EXISTS "{S}".runtime_builds')
    op.execute(f'DROP TABLE IF EXISTS "{S}".runtime_libraries')
