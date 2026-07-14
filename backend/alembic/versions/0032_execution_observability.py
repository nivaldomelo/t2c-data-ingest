"""executions: métricas first-class p/ observabilidade + quality_summary (pontos 14/15)

Revision ID: 0032_obs
Revises: 0031_ctrl
Create Date: 2026-07-14

Observabilidade rápida sem re-parsear logs: promove records_read/written e watermark
before/after a colunas, guarda quality_summary da execução, e indexa as colunas quentes usadas
pelo dashboard operacional. (control_id/source/target ids + summaries já vieram em 0029/0031.)
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0032_obs"
down_revision: Union[str, None] = "0031_ctrl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"
T = f'"{S}".executions'


def upgrade() -> None:
    for col in (
        "records_read BIGINT NULL",
        "records_written BIGINT NULL",
        "watermark_before TIMESTAMPTZ NULL",
        "watermark_after TIMESTAMPTZ NULL",
        "quality_summary JSONB NULL",
    ):
        op.execute(f"ALTER TABLE {T} ADD COLUMN IF NOT EXISTS {col}")
    for name, cols in (
        ("idx_executions_started_at", "started_at"),
        ("idx_executions_status_started", "status, started_at"),
        ("idx_executions_control_id", "control_id"),
        ("idx_executions_destination_id", "destination_id"),
        ("idx_executions_source_connection", "source_connection_id"),
        ("idx_executions_target_connection", "target_connection_id"),
    ):
        op.execute(f'CREATE INDEX IF NOT EXISTS {name} ON {T}({cols})')


def downgrade() -> None:
    for name in ("idx_executions_started_at", "idx_executions_status_started", "idx_executions_control_id",
                 "idx_executions_destination_id", "idx_executions_source_connection", "idx_executions_target_connection"):
        op.execute(f'DROP INDEX IF EXISTS "{S}".{name}')
    for col in ("records_read", "records_written", "watermark_before", "watermark_after", "quality_summary"):
        op.execute(f"ALTER TABLE {T} DROP COLUMN IF EXISTS {col}")
