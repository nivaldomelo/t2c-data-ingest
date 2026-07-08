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


class IngestionControlCreate(IngestionControlBase):
    pass


class IngestionControlUpdate(BaseModel):
    nome_tabela: str | None = None
    coluna_data: str | None = None
    coluna_ultima_alteracao: str | None = None
    grupo: str | None = None
    watermark_atual: datetime | None = None
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


class IngestionControlOut(IngestionControlBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None


class IngestionControlSummary(BaseModel):
    total: int
    ativas: int
    inativas: int
    incrementais: int
    ultimas_com_erro: int
