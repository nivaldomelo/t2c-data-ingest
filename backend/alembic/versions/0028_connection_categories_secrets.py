"""connections: connection_category + secrets_encrypted + deleted_at

Revision ID: 0028_conn_cat
Revises: 0027_dl
Create Date: 2026-07-12

Aditivo. Generaliza Conexões para categorias (database/storage/api) e novos conectores
(SQL Server, Oracle, MariaDB, MongoDB, REST API, Jira, Mixpanel, Blip). Segredos específicos de
tipo ficam num único blob cifrado (secrets_encrypted); nada de secret em claro. Backfill de
connection_category para as conexões existentes.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0028_conn_cat"
down_revision: Union[str, None] = "0027_dl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f'ALTER TABLE "{S}".connections ADD COLUMN IF NOT EXISTS connection_category varchar(20) NULL')
    op.execute(f'ALTER TABLE "{S}".connections ADD COLUMN IF NOT EXISTS secrets_encrypted text NULL')
    op.execute(f'ALTER TABLE "{S}".connections ADD COLUMN IF NOT EXISTS deleted_at timestamptz NULL')
    # Backfill da categoria a partir do tipo existente.
    op.execute(f"""
        UPDATE "{S}".connections SET connection_category = CASE
            WHEN connection_type IN ('postgres','mysql','sqlserver','oracle','mariadb','mongodb') THEN 'database'
            WHEN connection_type IN ('s3') THEN 'storage'
            WHEN connection_type IN ('rest_api','jira','mixpanel','blip') THEN 'api'
            ELSE 'database' END
        WHERE connection_category IS NULL
    """)
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_ingest_connections_category ON "{S}".connections (connection_category)')


def downgrade() -> None:
    op.execute(f'DROP INDEX IF EXISTS "{S}".ix_ingest_connections_category')
    op.execute(f'ALTER TABLE "{S}".connections DROP COLUMN IF EXISTS deleted_at')
    op.execute(f'ALTER TABLE "{S}".connections DROP COLUMN IF EXISTS secrets_encrypted')
    op.execute(f'ALTER TABLE "{S}".connections DROP COLUMN IF EXISTS connection_category')
