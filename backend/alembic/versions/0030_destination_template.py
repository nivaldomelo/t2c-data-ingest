"""destinations: is_template (destino reutilizável; a tabela vem em runtime)

Revision ID: 0030_dest_tpl
Revises: 0029_dest
Create Date: 2026-07-14

Um destino template padroniza o COMO (write_mode/formato/partição/upsert/camada/raiz) e recebe o
nome da tabela em runtime (Controle de Ingestão nome_tabela ou arg do job), com placeholder
{table}. Assim um punhado de destinos serve centenas/milhares de tabelas.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0030_dest_tpl"
down_revision: Union[str, None] = "0029_dest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f'ALTER TABLE "{S}".destinations ADD COLUMN IF NOT EXISTS is_template boolean NOT NULL DEFAULT false')


def downgrade() -> None:
    op.execute(f'ALTER TABLE "{S}".destinations DROP COLUMN IF EXISTS is_template')
