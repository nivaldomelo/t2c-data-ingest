"""runtime stack versions on clusters / runtime_builds / executions (Spark 4 migration)

Revision ID: 0024_vers
Revises: 0023_outbox
Create Date: 2026-07-10

Additive. Makes the Spark/Python/Java/Scala stack traceable per cluster, per build and per
execution — so you can tell which runtime actually ran each job (before/after Spark 4).
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0024_vers"
down_revision: Union[str, None] = "0023_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    for col in ("spark_version VARCHAR(50)", "python_version VARCHAR(50)",
                "java_version VARCHAR(50)", "scala_version VARCHAR(50)",
                "runtime_image VARCHAR(300)"):
        op.execute(f'ALTER TABLE "{S}".clusters ADD COLUMN IF NOT EXISTS {col}')
    for col in ("spark_version VARCHAR(50)", "python_version VARCHAR(50)",
                "java_version VARCHAR(50)", "scala_version VARCHAR(50)",
                "base_image VARCHAR(300)"):
        op.execute(f'ALTER TABLE "{S}".runtime_builds ADD COLUMN IF NOT EXISTS {col}')
    for col in ("spark_version VARCHAR(50)", "python_version VARCHAR(50)", "runtime_image VARCHAR(300)"):
        op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS {col}')


def downgrade() -> None:
    for c in ("spark_version", "python_version", "java_version", "scala_version", "runtime_image"):
        op.execute(f'ALTER TABLE "{S}".clusters DROP COLUMN IF EXISTS {c}')
    for c in ("spark_version", "python_version", "java_version", "scala_version", "base_image"):
        op.execute(f'ALTER TABLE "{S}".runtime_builds DROP COLUMN IF EXISTS {c}')
    for c in ("spark_version", "python_version", "runtime_image"):
        op.execute(f'ALTER TABLE "{S}".executions DROP COLUMN IF EXISTS {c}')
