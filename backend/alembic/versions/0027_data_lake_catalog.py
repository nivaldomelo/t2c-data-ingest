"""data lake catalog: catalogs/schemas/tables/columns/files/partitions + query history

Revision ID: 0027_dl
Revises: 0026_ic_s3
Create Date: 2026-07-10

Additive. Catálogo técnico do Data Lake (S3) estilo Databricks Catalog: camadas Bronze/Silver/
Gold como schemas, pastas como tabelas lógicas, arquivos Parquet como dados. Todo o conteúdo é
metadado — nenhum segredo é gravado aqui (as credenciais ficam na conexão S3).
"""
from typing import Sequence, Union

from alembic import op

from t2c_ingest.core.config import settings

revision: str = "0027_dl"
down_revision: Union[str, None] = "0026_ic_s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = settings.db_schema or "t2c_data_ingest"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".data_lake_catalogs (
            id SERIAL PRIMARY KEY,
            connection_id INTEGER NOT NULL,
            name VARCHAR(150) NOT NULL,
            description TEXT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            last_scan_status VARCHAR(30) NULL,
            last_scan_at TIMESTAMPTZ NULL,
            last_scan_message TEXT NULL,
            created_by VARCHAR(255) NULL,
            updated_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".data_lake_schemas (
            id SERIAL PRIMARY KEY,
            catalog_id INTEGER NOT NULL,
            schema_name VARCHAR(150) NOT NULL,
            layer_name VARCHAR(50) NULL,
            bucket_name VARCHAR(255) NOT NULL,
            base_prefix TEXT NOT NULL,
            description TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".data_lake_tables (
            id SERIAL PRIMARY KEY,
            schema_id INTEGER NOT NULL,
            table_name VARCHAR(255) NOT NULL,
            table_path TEXT NOT NULL,
            file_format VARCHAR(30) NOT NULL DEFAULT 'parquet',
            partition_columns JSONB NULL,
            columns_count INTEGER NULL,
            files_count INTEGER NULL,
            total_size_bytes BIGINT NULL,
            estimated_rows BIGINT NULL,
            last_modified_at TIMESTAMPTZ NULL,
            last_schema_scan_at TIMESTAMPTZ NULL,
            last_data_sample_at TIMESTAMPTZ NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".data_lake_columns (
            id SERIAL PRIMARY KEY,
            table_id INTEGER NOT NULL,
            column_name VARCHAR(255) NOT NULL,
            ordinal_position INTEGER NULL,
            spark_type VARCHAR(150) NULL,
            parquet_type VARCHAR(150) NULL,
            nullable BOOLEAN NULL,
            is_partition BOOLEAN NOT NULL DEFAULT FALSE,
            comment TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".data_lake_files (
            id SERIAL PRIMARY KEY,
            table_id INTEGER NOT NULL,
            partition_path TEXT NULL,
            object_key TEXT NOT NULL,
            size_bytes BIGINT NULL,
            last_modified_at TIMESTAMPTZ NULL,
            storage_class VARCHAR(50) NULL,
            etag VARCHAR(150) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".data_lake_partitions (
            id SERIAL PRIMARY KEY,
            table_id INTEGER NOT NULL,
            partition_path TEXT NOT NULL,
            partition_values JSONB NULL,
            files_count INTEGER NULL,
            total_size_bytes BIGINT NULL,
            last_modified_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL
        )
    """)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".data_lake_query_history (
            id SERIAL PRIMARY KEY,
            connection_id INTEGER NOT NULL,
            catalog_id INTEGER NULL,
            table_id INTEGER NULL,
            executed_sql TEXT NOT NULL,
            translated_sql TEXT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            started_at TIMESTAMPTZ NULL,
            finished_at TIMESTAMPTZ NULL,
            duration_seconds INTEGER NULL,
            rows_returned INTEGER NULL,
            limit_applied INTEGER NULL,
            result_preview JSONB NULL,
            error_message TEXT NULL,
            executed_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    # Execuções de varredura do catálogo (assíncronas, no worker). Poll por GET /scan-runs/{id}.
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS "{S}".data_lake_scan_runs (
            id SERIAL PRIMARY KEY,
            catalog_id INTEGER NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            started_at TIMESTAMPTZ NULL,
            finished_at TIMESTAMPTZ NULL,
            duration_seconds INTEGER NULL,
            stats JSONB NULL,
            message TEXT NULL,
            error_message TEXT NULL,
            requested_by VARCHAR(255) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    # Índices
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_schemas_catalog ON "{S}".data_lake_schemas(catalog_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_tables_schema ON "{S}".data_lake_tables(schema_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_tables_name ON "{S}".data_lake_tables(table_name)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_files_table ON "{S}".data_lake_files(table_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_files_last_modified ON "{S}".data_lake_files(last_modified_at)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_partitions_table ON "{S}".data_lake_partitions(table_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_columns_table ON "{S}".data_lake_columns(table_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_query_history_table ON "{S}".data_lake_query_history(table_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_catalogs_connection ON "{S}".data_lake_catalogs(connection_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_scan_runs_catalog ON "{S}".data_lake_scan_runs(catalog_id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_scan_runs_status ON "{S}".data_lake_scan_runs(status, id)')
    op.execute(f'CREATE INDEX IF NOT EXISTS idx_data_lake_query_history_status ON "{S}".data_lake_query_history(status, id)')


def downgrade() -> None:
    for t in (
        "data_lake_scan_runs", "data_lake_query_history", "data_lake_partitions",
        "data_lake_files", "data_lake_columns", "data_lake_tables", "data_lake_schemas",
        "data_lake_catalogs",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{S}".{t}')
