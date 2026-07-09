"""ingest tool access allowlist (admin-managed opt-in)

Revision ID: 0019_access
Revises: 0018_dq
Create Date: 2026-07-09

Additive/non-destructive. Table lives in the ingest schema. Access to the tool is opt-in:
admins always have access; everyone else needs a row here (view-only).
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0019_access"
down_revision: Union[str, None] = "0018_dq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".user_access (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            note TEXT NULL,
            active BOOLEAN NOT NULL DEFAULT true,
            granted_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS ix_ingest_user_access_email ON "{S}".user_access (email)')


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{S}".user_access')
