"""alerts: notification channels + notification history

Revision ID: 0017_alerts
Revises: 0016_backfill
Create Date: 2026-07-09

Additive/non-destructive.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0017_alerts"
down_revision: Union[str, None] = "0016_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".alert_channels (
            id SERIAL PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            channel_type VARCHAR(30) NOT NULL,
            target_url_encrypted TEXT NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            events JSONB NULL,
            min_severity VARCHAR(20) NOT NULL DEFAULT 'warning',
            created_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".alert_notifications (
            id SERIAL PRIMARY KEY,
            channel_id INTEGER NULL,
            event_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'warning',
            title TEXT NOT NULL,
            message TEXT NULL,
            job_id INTEGER NULL,
            pipeline_id INTEGER NULL,
            execution_id INTEGER NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            http_status INTEGER NULL,
            error TEXT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            sent_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_alert_notifications_status ON "{S}".alert_notifications (status, id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_alert_notifications_created ON "{S}".alert_notifications (created_at)')


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{S}".alert_notifications')
    op.execute(f'DROP TABLE IF EXISTS "{S}".alert_channels')
