"""multi-destino por carga: ingestion_control_destinations (carga multi-destino)

Revision ID: 0034_icdest
Revises: 0033_intev
Create Date: 2026-07-14

Additive. Permite que um registro do Controle de Ingestão grave em VÁRIOS destinos (ex.: cópia
no Data Lake S3 Bronze + destino relacional PostgreSQL), cada um com papel, ordem de escrita e
obrigatoriedade. Não altera o modelo de destino único existente (destination_id/destino_config no
controle continuam válidos); esta tabela é a forma declarativa de N destinos por carga.
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0034_icdest"
down_revision: Union[str, None] = "0033_intev"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    t = f'"{S}".ingestion_control_destinations'
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {t} (
            id SERIAL PRIMARY KEY,
            control_id INTEGER NOT NULL,
            destination_id INTEGER NOT NULL,
            destination_role VARCHAR(50) NOT NULL,
            write_order INTEGER NOT NULL DEFAULT 1,
            required BOOLEAN NOT NULL DEFAULT TRUE,
            stop_on_failure BOOLEAN NOT NULL DEFAULT TRUE,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_ic_destinations_control ON {t} (control_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_ic_destinations_destination ON {t} (destination_id)')
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS uq_ic_destination_role '
               f'ON {t} (control_id, destination_id, destination_role)')


def downgrade() -> None:
    op.execute(f'DROP TABLE IF EXISTS "{S}".ingestion_control_destinations')
