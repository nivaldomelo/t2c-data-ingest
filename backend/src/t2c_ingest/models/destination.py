"""Destination (Ingestion Target) — destino declarativo e reutilizável (DEST-1).

Um destino aponta para uma Connection e descreve, de forma governável, PARA ONDE e COMO gravar
(schema/tabela + write_mode/upsert para bancos; bucket/prefixo/camada/formato/partições para S3).
Nenhum segredo mora aqui — credenciais ficam na conexão.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base

DESTINATION_TYPES = ("postgres", "s3")
PG_WRITE_MODES = ("append", "overwrite", "truncate_insert", "upsert", "merge")
S3_WRITE_MODES = ("append", "overwrite", "overwrite_partitions", "error_if_exists", "ignore")


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    destination_type: Mapped[str] = mapped_column(String(50), nullable=False)
    connection_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Banco relacional
    target_schema: Mapped[str | None] = mapped_column(String(150))
    target_table: Mapped[str | None] = mapped_column(String(255))
    target_database: Mapped[str | None] = mapped_column(String(150))

    # S3 / Data Lake
    target_bucket: Mapped[str | None] = mapped_column(String(255))
    target_prefix: Mapped[str | None] = mapped_column(Text)
    target_path: Mapped[str | None] = mapped_column(Text)
    target_layer: Mapped[str | None] = mapped_column(String(50))

    file_format: Mapped[str | None] = mapped_column(String(50))
    write_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="append", server_default="append")
    compression: Mapped[str | None] = mapped_column(String(50))

    partition_columns: Mapped[list | None] = mapped_column(JSONB)
    primary_key_columns: Mapped[list | None] = mapped_column(JSONB)

    staging_schema: Mapped[str | None] = mapped_column(String(150))
    staging_table: Mapped[str | None] = mapped_column(String(255))
    upsert_strategy: Mapped[str | None] = mapped_column(String(50))
    truncate_before_load: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    options: Mapped[dict | None] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    last_test_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_tested", server_default="not_tested")
    last_test_message: Mapped[str | None] = mapped_column(Text)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(255))
    deleted_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
