"""integration outbox (reliable push to t2c_data)

Revision ID: 0023_outbox
Revises: 0022_hb
Create Date: 2026-07-09

Additive. Decouples the ingest->t2c_data push: producers write an outbox row in the SAME
transaction as their local write; a publisher delivers it with retry and alerts on persistent
failure — instead of a fire-and-forget cross-schema INSERT that swallowed errors.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0023_outbox"
down_revision: Union[str, None] = "0022_hb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".integration_outbox (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(50) NOT NULL,
            payload JSONB NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            error TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            sent_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_outbox_status ON "{S}".integration_outbox (status, id)')


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{S}".integration_outbox')
