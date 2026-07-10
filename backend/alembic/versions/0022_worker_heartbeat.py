"""worker heartbeat (for WORKER_DOWN detection)

Revision ID: 0022_hb
Revises: 0021_exec
Create Date: 2026-07-09

Additive. Each worker upserts its last_seen every tick; the scheduler (a separate process)
raises WORKER_DOWN when no worker heartbeat is recent.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0022_hb"
down_revision: Union[str, None] = "0021_exec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".worker_heartbeats (
            worker_id VARCHAR(120) PRIMARY KEY,
            last_seen TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{S}".worker_heartbeats')
