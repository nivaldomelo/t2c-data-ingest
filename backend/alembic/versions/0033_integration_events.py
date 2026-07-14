"""integration outbox v2 (multi-event) + generic events sink in t2c_data (ponto 16)

Revision ID: 0033_intev
Revises: 0032_obs
Create Date: 2026-07-14

Additive. Evolves the reliable outbox to carry MANY event types (lineage, data quality, schema,
S3/Data Lake, operational incidents) with idempotency and proper retry/backoff/dead-letter, and
adds a generic events sink (t2c_data.ingest_events) so t2c_data receives ALL operational metadata
even before it grows dedicated tables. Nothing here removes the lineage path — old rows keep
delivering to t2c_data.ingest_lineage.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0033_intev"
down_revision: Union[str, None] = "0032_obs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"
R = settings.reference_schema or "t2c_data"


def upgrade() -> None:
    ob = f'"{S}".integration_outbox'
    # Widen event_type (100) and add the columns the recommended outbox model expects.
    op.execute(f'ALTER TABLE {ob} ALTER COLUMN event_type TYPE VARCHAR(100)')
    op.execute(f"ALTER TABLE {ob} ADD COLUMN IF NOT EXISTS aggregate_type VARCHAR(100) NULL")
    op.execute(f"ALTER TABLE {ob} ADD COLUMN IF NOT EXISTS aggregate_id VARCHAR(150) NULL")
    op.execute(f"ALTER TABLE {ob} ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 5")
    op.execute(f"ALTER TABLE {ob} ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NULL")
    op.execute(f"ALTER TABLE {ob} ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ NULL")
    op.execute(f"ALTER TABLE {ob} ADD COLUMN IF NOT EXISTS dead_at TIMESTAMPTZ NULL")
    op.execute(f"ALTER TABLE {ob} ADD COLUMN IF NOT EXISTS error_message TEXT NULL")
    op.execute(f"ALTER TABLE {ob} ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255) NULL")
    op.execute(f"ALTER TABLE {ob} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NULL")
    # Backfill next_attempt_at for existing pending/failed rows so the new scheduler picks them up.
    op.execute(f"UPDATE {ob} SET next_attempt_at = COALESCE(next_attempt_at, created_at) "
               f"WHERE status IN ('pending', 'failed')")

    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_outbox_next_attempt ON {ob} (next_attempt_at)')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_outbox_event_type ON {ob} (event_type)')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_outbox_aggregate ON {ob} (aggregate_type, aggregate_id)')
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS uq_ingest_outbox_idempotency ON {ob} (idempotency_key) '
               f'WHERE idempotency_key IS NOT NULL')

    # Generic operational-events sink in t2c_data. All event types land here (idempotent), so the
    # base product can build catalog/governance/lineage from real ingest runs. Dedicated tables in
    # t2c_data (lineage/quality/catalog/incidents) can consume from this later.
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{R}".ingest_events (
            id BIGSERIAL PRIMARY KEY,
            event_type VARCHAR(100) NOT NULL,
            aggregate_type VARCHAR(100) NULL,
            aggregate_id VARCHAR(150) NULL,
            idempotency_key VARCHAR(255) NULL,
            source VARCHAR(50) NOT NULL DEFAULT 't2c_data_ingest',
            payload JSONB NOT NULL,
            occurred_at TIMESTAMPTZ NULL,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_t2cdata_ingest_events_type ON "{R}".ingest_events (event_type, id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_t2cdata_ingest_events_aggregate '
               f'ON "{R}".ingest_events (aggregate_type, aggregate_id)')
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS uq_t2cdata_ingest_events_idempotency '
               f'ON "{R}".ingest_events (idempotency_key) WHERE idempotency_key IS NOT NULL')


def downgrade() -> None:
    ob = f'"{S}".integration_outbox'
    op.execute(f'DROP INDEX IF EXISTS "{S}".uq_ingest_outbox_idempotency')
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_ingest_outbox_aggregate')
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_ingest_outbox_event_type')
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_ingest_outbox_next_attempt')
    for col in ("aggregate_type", "aggregate_id", "max_attempts", "next_attempt_at",
                "last_attempt_at", "dead_at", "error_message", "idempotency_key", "updated_at"):
        op.execute(f"ALTER TABLE {ob} DROP COLUMN IF EXISTS {col}")
    op.execute(f'DROP TABLE IF EXISTS "{R}".ingest_events')
