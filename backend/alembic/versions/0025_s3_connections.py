"""AWS S3 / Data Lake connection support (encrypted creds + read/write flags)

Revision ID: 0025_s3
Revises: 0024_vers
Create Date: 2026-07-10

Additive. Adds encrypted AWS credential columns and can_read/can_write to connections so S3 can
be a first-class connection type. Non-secret S3 config (region/bucket/prefix/layer/auth_mode/
role_arn/endpoint) lives in the existing extra_params JSONB. No data changes.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0025_s3"
down_revision: Union[str, None] = "0024_vers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f'ALTER TABLE "{S}".connections ADD COLUMN IF NOT EXISTS aws_access_key_id_encrypted TEXT NULL')
    op.execute(f'ALTER TABLE "{S}".connections ADD COLUMN IF NOT EXISTS aws_secret_access_key_encrypted TEXT NULL')
    op.execute(f'ALTER TABLE "{S}".connections ADD COLUMN IF NOT EXISTS aws_session_token_encrypted TEXT NULL')
    op.execute(f'ALTER TABLE "{S}".connections ADD COLUMN IF NOT EXISTS can_read BOOLEAN NOT NULL DEFAULT TRUE')
    op.execute(f'ALTER TABLE "{S}".connections ADD COLUMN IF NOT EXISTS can_write BOOLEAN NOT NULL DEFAULT FALSE')
    # extra_params already exists.


def downgrade() -> None:
    for c in ("aws_access_key_id_encrypted", "aws_secret_access_key_encrypted",
              "aws_session_token_encrypted", "can_read", "can_write"):
        op.execute(f'ALTER TABLE "{S}".connections DROP COLUMN IF EXISTS {c}')
