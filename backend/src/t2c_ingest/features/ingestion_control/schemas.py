from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IngestionControlBase(BaseModel):
    nome_tabela: str = Field(min_length=1)
    coluna_data: str | None = None
    coluna_ultima_alteracao: str | None = None
    grupo: str | None = None
    watermark_atual: datetime | None = None
    ultima_execucao: datetime | None = None
    status: str | None = None
    observacao: str | None = None
    ativo: bool | None = True
    tipo_tabela: str | None = None
    origem: str | None = None
    destino: str | None = None
    dados_sensiveis: str | None = None
    tipo_ingestao: str | None = None
    colunas_chave: str | None = None
    origem_id: str | None = None
    # Destino S3/Data Lake: conexão de destino + bag de configuração (bucket/prefixo/camada/
    # formato/write_mode/partições/compressão). Sem segredos — credenciais ficam na conexão.
    destino_id: str | None = None
    destino_config: dict | None = None
    destination_id: int | None = None
    # ── CTRL-1: descrição declarativa ──
    source_connection_id: int | None = None
    target_connection_id: int | None = None
    source_database: str | None = None
    source_schema: str | None = None
    source_table: str | None = None
    source_query: str | None = None
    source_path: str | None = None
    source_file_format: str | None = None
    target_database: str | None = None
    target_schema: str | None = None
    target_table: str | None = None
    staging_schema: str | None = None
    staging_table: str | None = None
    target_bucket: str | None = None
    target_prefix: str | None = None
    target_path: str | None = None
    target_layer: str | None = None
    file_format: str | None = None
    compression: str | None = None
    partition_columns: list[str] | None = None
    write_mode: str | None = None
    upsert_strategy: str | None = None
    truncate_before_load: bool | None = False
    expected_frequency: str | None = None
    expected_frequency_minutes: int | None = None
    owner_name: str | None = None
    owner_email: str | None = None
    sla_minutes: int | None = None
    criticality: str | None = None
    extra_params: dict | None = None


class IngestionControlCreate(IngestionControlBase):
    pass


class IngestionControlUpdate(BaseModel):
    # NOTE: watermark_atual is intentionally NOT updatable here. Resetting the watermark must
    # flow through the permission-gated, audited backfill endpoint (INGEST_BACKFILL_WATERMARK)
    # so the change is authorized and recorded — not silently via a routine control edit.
    nome_tabela: str | None = None
    coluna_data: str | None = None
    coluna_ultima_alteracao: str | None = None
    grupo: str | None = None
    ultima_execucao: datetime | None = None
    status: str | None = None
    observacao: str | None = None
    ativo: bool | None = None
    tipo_tabela: str | None = None
    origem: str | None = None
    destino: str | None = None
    dados_sensiveis: str | None = None
    tipo_ingestao: str | None = None
    colunas_chave: str | None = None
    origem_id: str | None = None
    destino_id: str | None = None
    destino_config: dict | None = None
    destination_id: int | None = None
    source_connection_id: int | None = None
    target_connection_id: int | None = None
    source_database: str | None = None
    source_schema: str | None = None
    source_table: str | None = None
    source_query: str | None = None
    source_path: str | None = None
    source_file_format: str | None = None
    target_database: str | None = None
    target_schema: str | None = None
    target_table: str | None = None
    staging_schema: str | None = None
    staging_table: str | None = None
    target_bucket: str | None = None
    target_prefix: str | None = None
    target_path: str | None = None
    target_layer: str | None = None
    file_format: str | None = None
    compression: str | None = None
    partition_columns: list[str] | None = None
    write_mode: str | None = None
    upsert_strategy: str | None = None
    truncate_before_load: bool | None = None
    expected_frequency: str | None = None
    expected_frequency_minutes: int | None = None
    owner_name: str | None = None
    owner_email: str | None = None
    sla_minutes: int | None = None
    criticality: str | None = None
    extra_params: dict | None = None


class IngestionControlOut(IngestionControlBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
    # Resumos resolvidos (não-secretos) de origem/destino para a UI/API.
    source: dict | None = None
    target: dict | None = None


class IngestionControlSummary(BaseModel):
    total: int
    ativas: int
    inativas: int
    incrementais: int
    ultimas_com_erro: int
