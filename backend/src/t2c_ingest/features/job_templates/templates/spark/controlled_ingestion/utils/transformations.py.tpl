"""Transformações específicas do job {{ job_name }}.

Ponto SEGURO para regras de negócio. Regras:
  - Não logar dados de negócio nem amostras sensíveis.
  - Não imprimir payloads completos.
  - Nunca colocar secrets aqui (o worker resolve credenciais em runtime).
"""
from __future__ import annotations

from pyspark.sql import DataFrame


def apply_transformations(df: DataFrame, control: dict) -> DataFrame:
    """Aplique aqui limpezas/derivações. Por padrão, passa o DataFrame adiante sem alterar.

    `control` traz os metadados da carga (nome_tabela, tipo_ingestao, source, destinations).
    """
    # TODO: implementar transformações específicas de {{ control_name }}.
    return df
