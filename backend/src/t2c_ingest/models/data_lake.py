"""Data Lake catalog models (ingest schema).

Modela o Data Lake (S3) como um catálogo técnico estilo Databricks: um catálogo por conexão S3,
camadas Bronze/Silver/Gold como schemas, pastas como tabelas lógicas, e os arquivos Parquet
como dados. Tudo aqui é metadado — nenhum segredo é gravado (credenciais ficam na conexão S3).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base


class DataLakeCatalog(Base):
    """Um catálogo do Data Lake, vinculado a uma conexão S3."""

    __tablename__ = "data_lake_catalogs"
    __table_args__ = (Index("idx_data_lake_catalogs_connection", "connection_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_scan_status: Mapped[str | None] = mapped_column(String(30))
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scan_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class DataLakeSchema(Base):
    """Uma camada/schema lógico (bronze/silver/gold) dentro de um catálogo."""

    __tablename__ = "data_lake_schemas"
    __table_args__ = (Index("idx_data_lake_schemas_catalog", "catalog_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_name: Mapped[str] = mapped_column(String(150), nullable=False)
    layer_name: Mapped[str | None] = mapped_column(String(50))
    bucket_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class DataLakeTable(Base):
    """Uma tabela lógica (pasta) dentro de um schema."""

    __tablename__ = "data_lake_tables"
    __table_args__ = (
        Index("idx_data_lake_tables_schema", "schema_id"),
        Index("idx_data_lake_tables_name", "table_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schema_id: Mapped[int] = mapped_column(Integer, nullable=False)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_format: Mapped[str] = mapped_column(String(30), nullable=False, default="parquet", server_default="parquet")
    partition_columns: Mapped[list | None] = mapped_column(JSONB)
    columns_count: Mapped[int | None] = mapped_column(Integer)
    files_count: Mapped[int | None] = mapped_column(Integer)
    total_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    estimated_rows: Mapped[int | None] = mapped_column(BigInteger)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_schema_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_data_sample_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class DataLakeColumn(Base):
    """Uma coluna do schema Parquet inferido de uma tabela."""

    __tablename__ = "data_lake_columns"
    __table_args__ = (Index("idx_data_lake_columns_table", "table_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ordinal_position: Mapped[int | None] = mapped_column(Integer)
    spark_type: Mapped[str | None] = mapped_column(String(150))
    parquet_type: Mapped[str | None] = mapped_column(String(150))
    nullable: Mapped[bool | None] = mapped_column(Boolean)
    is_partition: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class DataLakeFile(Base):
    """Um arquivo (objeto S3) pertencente a uma tabela."""

    __tablename__ = "data_lake_files"
    __table_args__ = (
        Index("idx_data_lake_files_table", "table_id"),
        Index("idx_data_lake_files_last_modified", "last_modified_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(Integer, nullable=False)
    partition_path: Mapped[str | None] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    storage_class: Mapped[str | None] = mapped_column(String(50))
    etag: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DataLakePartition(Base):
    """Uma partição detectada de uma tabela."""

    __tablename__ = "data_lake_partitions"
    __table_args__ = (Index("idx_data_lake_partitions_table", "table_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(Integer, nullable=False)
    partition_path: Mapped[str] = mapped_column(Text, nullable=False)
    partition_values: Mapped[dict | None] = mapped_column(JSONB)
    files_count: Mapped[int | None] = mapped_column(Integer)
    total_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class DataLakeQueryHistory(Base):
    """Histórico de consultas rápidas (read-only) executadas no Data Lake. A própria linha é o
    registro da execução assíncrona: nasce 'queued', o worker a processa e grava o resultado."""

    __tablename__ = "data_lake_query_history"
    __table_args__ = (
        Index("idx_data_lake_query_history_table", "table_id"),
        Index("idx_data_lake_query_history_status", "status", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(Integer, nullable=False)
    catalog_id: Mapped[int | None] = mapped_column(Integer)
    table_id: Mapped[int | None] = mapped_column(Integer)
    executed_sql: Mapped[str] = mapped_column(Text, nullable=False)
    translated_sql: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", server_default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    rows_returned: Mapped[int | None] = mapped_column(Integer)
    limit_applied: Mapped[int | None] = mapped_column(Integer)
    result_preview: Mapped[dict | None] = mapped_column(JSONB)  # {columns:[...], rows:[...]}
    error_message: Mapped[str | None] = mapped_column(Text)
    executed_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DataLakeScanRun(Base):
    """Uma execução de varredura do catálogo (assíncrona, no worker). Nasce 'queued'."""

    __tablename__ = "data_lake_scan_runs"
    __table_args__ = (
        Index("idx_data_lake_scan_runs_catalog", "catalog_id"),
        Index("idx_data_lake_scan_runs_status", "status", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", server_default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    stats: Mapped[dict | None] = mapped_column(JSONB)
    message: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
