"""Renderização segura de templates `{{ chave }}`.

Substitui APENAS ocorrências de `{{ chave }}` (chave = identificador) por valores de um dict
achatado. Chaves de código Python com chaves simples `{}` (f-strings, dicts) ficam intactas.
Sem eval/execução: é só substituição textual controlada.
"""
from __future__ import annotations

import re

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render(template_text: str, context: dict) -> str:
    """Substitui `{{ chave }}` por context[chave] (vazio se ausente)."""
    def _sub(match: re.Match) -> str:
        return to_text(context.get(match.group(1)))
    return _PLACEHOLDER.sub(_sub, template_text)
