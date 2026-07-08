"""cluster libraries: managed pip packages + install history + job links

Revision ID: 0012_libraries
Revises: 0011_soft_delete
Create Date: 2026-07-08

Additive/non-destructive.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0012_libraries"
down_revision: Union[str, None] = "0011_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".cluster_libraries (
            id SERIAL PRIMARY KEY,
            cluster_id INTEGER NULL,
            package_name VARCHAR(200) NOT NULL,
            package_version VARCHAR(100) NULL,
            package_spec VARCHAR(300) NOT NULL,
            source VARCHAR(30) NOT NULL DEFAULT 'pypi',
            install_scope VARCHAR(30) NOT NULL DEFAULT 'cluster',
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            note TEXT NULL,
            installed_at TIMESTAMPTZ NULL,
            installed_by VARCHAR(255) NULL,
            removed_at TIMESTAMPTZ NULL,
            removed_by VARCHAR(255) NULL,
            last_action_at TIMESTAMPTZ NULL,
            last_action_status VARCHAR(30) NULL,
            last_action_message TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(
        f'CREATE UNIQUE INDEX IF NOT EXISTS uq_ingest_cluster_libraries_pkg '
        f'ON "{S}".cluster_libraries (package_name, COALESCE(cluster_id, -1))'
    )
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".cluster_library_actions (
            id SERIAL PRIMARY KEY,
            library_id INTEGER NULL,
            cluster_id INTEGER NULL,
            action VARCHAR(30) NOT NULL,
            package_spec VARCHAR(300) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            started_at TIMESTAMPTZ NULL,
            finished_at TIMESTAMPTZ NULL,
            duration_seconds INTEGER NULL,
            command_safe TEXT NULL,
            logs TEXT NULL,
            error_message TEXT NULL,
            requested_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        f'CREATE INDEX IF NOT EXISTS ix_ingest_cluster_library_actions_lib '
        f'ON "{S}".cluster_library_actions (library_id, id)'
    )
    op.execute(
        f'CREATE INDEX IF NOT EXISTS ix_ingest_cluster_library_actions_status '
        f'ON "{S}".cluster_library_actions (status, id)'
    )
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".job_libraries (
            id SERIAL PRIMARY KEY,
            job_id INTEGER NOT NULL,
            library_id INTEGER NOT NULL,
            required BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        f'CREATE UNIQUE INDEX IF NOT EXISTS uq_ingest_job_libraries '
        f'ON "{S}".job_libraries (job_id, library_id)'
    )


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{S}".job_libraries')
    op.execute(f'DROP TABLE IF EXISTS "{S}".cluster_library_actions')
    op.execute(f'DROP TABLE IF EXISTS "{S}".cluster_libraries')
