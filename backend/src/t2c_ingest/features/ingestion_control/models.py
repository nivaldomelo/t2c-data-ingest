from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, MetaData, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from t2c_ingest.core.config import settings

# Dedicated metadata bound to the `controle` schema. This table is OWNED by the operational
# control plane (schema `controle`) and is intentionally NOT on the ingest Base metadata, so
# the ingest Alembic autogenerate never touches it. It is created by a hand-written migration.
controle_metadata = MetaData(schema=settings.controle_schema)


class ControleBase(DeclarativeBase):
    metadata = controle_metadata


# Suggested value sets (used by the frontend selects; text is not hard-blocked server-side).
STATUS_VALUES = ("PENDENTE", "ATIVO", "EM_EXECUCAO", "SUCESSO", "ERRO", "INATIVO", "PAUSADO")
TIPO_TABELA_VALUES = ("FULL", "INCREMENTAL", "DIMENSAO", "FATO", "CONTROLE", "LOG")
TIPO_INGESTAO_VALUES = ("FULL", "INCREMENTAL", "CDC", "D-1", "MANUAL")
ORIGEM_VALUES = ("MYSQL", "POSTGRES", "SQLSERVER", "ORACLE", "API", "S3", "CSV", "PARQUET")
DESTINO_VALUES = ("BRONZE", "SILVER", "GOLD", "POSTGRES", "S3", "DATALAKE")


class IngestionControl(ControleBase):
    __tablename__ = "t2c_data_controle_ingestao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome_tabela: Mapped[str] = mapped_column(Text, nullable=False)
    coluna_data: Mapped[str | None] = mapped_column(String(100))
    coluna_ultima_alteracao: Mapped[str | None] = mapped_column(String(100))
    grupo: Mapped[str | None] = mapped_column(String(50))
    watermark_atual: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    ultima_execucao: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    status: Mapped[str | None] = mapped_column(String(20))
    observacao: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool | None] = mapped_column(Boolean)
    criado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    tipo_tabela: Mapped[str | None] = mapped_column(String(20))
    origem: Mapped[str | None] = mapped_column(String(20))
    destino: Mapped[str | None] = mapped_column(String(20))
    dados_sensiveis: Mapped[str | None] = mapped_column(Text)
    tipo_ingestao: Mapped[str | None] = mapped_column(Text)
    colunas_chave: Mapped[str | None] = mapped_column(Text)
    origem_id: Mapped[str | None] = mapped_column(Text)
    # Conexão de destino (id, mesmo padrão texto de origem_id) e configuração de destino S3/Data
    # Lake (bucket/prefixo/camada/formato/write_mode/partições/compressão) num único JSONB.
    destino_id: Mapped[str | None] = mapped_column(Text)
    destino_config: Mapped[dict | None] = mapped_column(JSONB)
    # Destino configurável (DEST-1) — referência à entidade t2c_data_ingest.destinations.
    destination_id: Mapped[int | None] = mapped_column(Integer)

    # ── CTRL-1: descrição declarativa completa da carga ──
    # Conexões de origem/destino (referenciam connections.id; credenciais ficam na conexão).
    source_connection_id: Mapped[int | None] = mapped_column(Integer)
    target_connection_id: Mapped[int | None] = mapped_column(Integer)
    # Origem
    source_database: Mapped[str | None] = mapped_column(String(150))
    source_schema: Mapped[str | None] = mapped_column(String(150))
    source_table: Mapped[str | None] = mapped_column(String(255))
    source_query: Mapped[str | None] = mapped_column(Text)
    source_path: Mapped[str | None] = mapped_column(Text)
    source_file_format: Mapped[str | None] = mapped_column(String(50))
    # Destino relacional
    target_database: Mapped[str | None] = mapped_column(String(150))
    target_schema: Mapped[str | None] = mapped_column(String(150))
    target_table: Mapped[str | None] = mapped_column(String(255))
    staging_schema: Mapped[str | None] = mapped_column(String(150))
    staging_table: Mapped[str | None] = mapped_column(String(255))
    # Destino S3 / Data Lake
    target_bucket: Mapped[str | None] = mapped_column(String(255))
    target_prefix: Mapped[str | None] = mapped_column(Text)
    target_path: Mapped[str | None] = mapped_column(Text)
    target_layer: Mapped[str | None] = mapped_column(String(50))
    file_format: Mapped[str | None] = mapped_column(String(50))
    compression: Mapped[str | None] = mapped_column(String(50))
    partition_columns: Mapped[list | None] = mapped_column(JSONB)
    # Estratégia de escrita
    write_mode: Mapped[str | None] = mapped_column(String(50))
    upsert_strategy: Mapped[str | None] = mapped_column(String(50))
    truncate_before_load: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Frequência / owner / SLA
    expected_frequency: Mapped[str | None] = mapped_column(String(50))
    expected_frequency_minutes: Mapped[int | None] = mapped_column(Integer)
    owner_name: Mapped[str | None] = mapped_column(String(150))
    owner_email: Mapped[str | None] = mapped_column(String(255))
    sla_minutes: Mapped[int | None] = mapped_column(Integer)
    criticality: Mapped[str | None] = mapped_column(String(30))
    # Configuração flexível adicional
    extra_params: Mapped[dict | None] = mapped_column(JSONB)
