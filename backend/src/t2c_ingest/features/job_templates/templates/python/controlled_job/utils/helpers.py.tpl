"""Helpers do job {{ job_name }}.

Ponto SEGURO para transformações/validações. Não logar dados sensíveis nem payloads completos.
"""
from __future__ import annotations


def transform_records(records: list, control: dict) -> list:
    """Transformações seguras. Por padrão, passa os registros adiante sem alterar."""
    # TODO: implementar transformações específicas de {{ control_name }}.
    return records
