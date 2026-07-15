"""segurança: correlation_id em execuções + criptografia S3 no destino

Revision ID: 0035_sec
Revises: 0034_icdest
Create Date: 2026-07-15

Additive. correlation_id p/ rastreabilidade sem expor dados; encryption_mode/kms_key_id no destino
S3 (SSE-S3/SSE-KMS) — o KMS key id NÃO é secreto; a chave em si nunca é armazenada.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0035_sec"
down_revision: Union[str, None] = "0034_icdest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f'ALTER TABLE "{S}".executions ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(64)')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_executions_correlation ON "{S}".executions (correlation_id)')
    op.execute(f'ALTER TABLE "{S}".destinations ADD COLUMN IF NOT EXISTS encryption_mode VARCHAR(20)')
    op.execute(f'ALTER TABLE "{S}".destinations ADD COLUMN IF NOT EXISTS kms_key_id VARCHAR(300)')


def downgrade() -> None:
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_executions_correlation')
    op.execute(f'ALTER TABLE "{S}".executions DROP COLUMN IF EXISTS correlation_id')
    op.execute(f'ALTER TABLE "{S}".destinations DROP COLUMN IF EXISTS encryption_mode')
    op.execute(f'ALTER TABLE "{S}".destinations DROP COLUMN IF EXISTS kms_key_id')
