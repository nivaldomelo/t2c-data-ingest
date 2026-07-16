"""overrides por-carga no vínculo: ingestion_control_destinations

Revision ID: 0036_icovr
Revises: 0035_sec
Create Date: 2026-07-16

Additive. O Destino passa a ser genérico (banco/schema ou bucket/prefixo/camada). O detalhe
por-carga (tabela, path relativo, partição, chave, staging, write mode/formato específicos) passa
a viver no vínculo carga↔destino, permitindo que poucos destinos reutilizáveis sirvam N tabelas.
Retrocompatível: colunas nullable; quando nulas, o runner cai de volta aos campos do destino.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0036_icovr"
down_revision: Union[str, None] = "0035_sec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    t = f'"{S}".ingestion_control_destinations'
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS target_schema VARCHAR(150)')
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS target_table VARCHAR(255)')
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS target_relative_path TEXT')
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS write_mode VARCHAR(50)')
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS file_format VARCHAR(50)')
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS compression VARCHAR(50)')
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS partition_columns JSONB')
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS primary_key_columns JSONB')
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS staging_table VARCHAR(255)')
    op.execute(f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS options JSONB')


def downgrade() -> None:
    t = f'"{S}".ingestion_control_destinations'
    for col in (
        "target_schema", "target_table", "target_relative_path", "write_mode", "file_format",
        "compression", "partition_columns", "primary_key_columns", "staging_table", "options",
    ):
        op.execute(f'ALTER TABLE {t} DROP COLUMN IF EXISTS {col}')
