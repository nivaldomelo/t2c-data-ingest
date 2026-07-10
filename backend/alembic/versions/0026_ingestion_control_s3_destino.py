"""controle: destino_id + destino_config (JSONB) para destino S3/Data Lake

Revision ID: 0026_ic_s3
Revises: 0025_s3_connections
Create Date: 2026-07-10

Non-destructive: ADD COLUMN IF NOT EXISTS. Guarda a config de destino S3 (bucket/prefixo/
camada/formato/write_mode/partições/compressão) num único JSONB, espelhando extra_params das
conexões; destino_id referencia a conexão de destino (mesmo padrão de origem_id, texto).
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0026_ic_s3"
down_revision: Union[str, None] = "0025_s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONTROLE = settings.controle_schema or "controle"
TABLE = f'"{CONTROLE}".t2c_data_controle_ingestao'


def upgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS destino_id text NULL")
    op.execute(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS destino_config jsonb NULL")


def downgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS destino_config")
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS destino_id")
