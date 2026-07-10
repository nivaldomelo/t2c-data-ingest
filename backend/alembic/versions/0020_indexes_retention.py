"""performance indexes + variables uniqueness

Revision ID: 0020_idx
Revises: 0019_access
Create Date: 2026-07-09

Additive/non-destructive. Adds the indexes that hot query paths rely on (declared on models but
never emitted by the hand-written migrations) and a uniqueness guard on variables. All created
IF NOT EXISTS so re-runs are safe. No data changes.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0020_idx"
down_revision: Union[str, None] = "0019_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    ix = [
        # executions: filtered/ordered by created_at on almost every endpoint.
        f'CREATE INDEX IF NOT EXISTS ix_ingest_executions_created_at ON "{S}".executions (created_at)',
        f'CREATE INDEX IF NOT EXISTS ix_ingest_executions_status_created ON "{S}".executions (status, created_at)',
        f'CREATE INDEX IF NOT EXISTS ix_ingest_executions_ttype_created ON "{S}".executions (target_type, created_at)',
        # audit: the Auditoria screen filters exactly by these (declared on model, never emitted).
        f'CREATE INDEX IF NOT EXISTS ix_ingest_audit_entity ON "{S}".audit_events (entity_type, entity_id)',
        f'CREATE INDEX IF NOT EXISTS ix_ingest_audit_user ON "{S}".audit_events (user_email)',
        # pipeline step executions: read on every execution detail + dashboard.
        f'CREATE INDEX IF NOT EXISTS ix_ingest_pse_execution ON "{S}".pipeline_step_executions (execution_id)',
        # per-screen filters.
        f'CREATE INDEX IF NOT EXISTS ix_ingest_dq_results_job_created ON "{S}".dq_results (job_id, created_at)',
        f'CREATE INDEX IF NOT EXISTS ix_ingest_backfill_runs_job ON "{S}".backfill_runs (job_id)',
        f'CREATE INDEX IF NOT EXISTS ix_ingest_alert_notif_channel ON "{S}".alert_notifications (channel_id, event_type)',
    ]
    for stmt in ix:
        op.execute(stmt)
    # variables: prevent duplicate (name, scope, environment); NULL environment treated as ''.
    op.execute(
        f'CREATE UNIQUE INDEX IF NOT EXISTS uq_ingest_variables_key '
        f'ON "{S}".variables (name, scope, COALESCE(environment, \'\'))'
    )


def downgrade() -> None:
    for name in [
        "ix_ingest_executions_created_at", "ix_ingest_executions_status_created",
        "ix_ingest_executions_ttype_created", "ix_ingest_audit_entity", "ix_ingest_audit_user",
        "ix_ingest_pse_execution", "ix_ingest_dq_results_job_created",
        "ix_ingest_backfill_runs_job", "ix_ingest_alert_notif_channel", "uq_ingest_variables_key",
    ]:
        op.execute(f'DROP INDEX IF EXISTS "{S}".{name}')
