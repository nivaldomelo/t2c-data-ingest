"""Catálogo de templates de job (MVP: 2 templates controlados).

Cada template mapeia um diretório sob `templates/` para um conjunto de arquivos-alvo do workspace.
`source` é o caminho do arquivo `.tpl`; `target` é o caminho relativo gerado no workspace do job.
"""
from __future__ import annotations

from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


TEMPLATES: list[dict] = [
    {
        "id": "spark_controlled_ingestion",
        "name": "Spark · Ingestão controlada pelo Controle de Ingestão",
        "engine": "spark_cluster",
        "job_type": "spark_python",
        "description": ("Job Spark declarativo (MySQL/Postgres → PostgreSQL + cópia Data Lake), "
                        "dirigido pelo Controle de Ingestão: origem, destinos, incremental e watermark."),
        "dir": "spark/controlled_ingestion",
        "files": [
            {"source": "main.py.tpl", "target": "main.py"},
            {"source": "README.md.tpl", "target": "README.md"},
            {"source": "config.example.json.tpl", "target": "config.example.json"},
            {"source": "utils/transformations.py.tpl", "target": "utils/transformations.py"},
        ],
        "requires_control": True,
    },
    {
        "id": "python_controlled_job",
        "name": "Python · Job genérico controlado",
        "engine": "python_worker",
        "job_type": "python",
        "description": ("Job Python leve controlado pelo Controle de Ingestão (APIs, Jira, Mixpanel, "
                        "Blip, REST genérica, jobs leves)."),
        "dir": "python/controlled_job",
        "files": [
            {"source": "main.py.tpl", "target": "main.py"},
            {"source": "README.md.tpl", "target": "README.md"},
            {"source": "config.example.json.tpl", "target": "config.example.json"},
            {"source": "utils/helpers.py.tpl", "target": "utils/helpers.py"},
        ],
        "requires_control": True,
    },
]

_BY_ID = {t["id"]: t for t in TEMPLATES}


def list_templates() -> list[dict]:
    return [{k: v for k, v in t.items() if k not in ("dir", "files")} for t in TEMPLATES]


def get_template(template_id: str) -> dict | None:
    return _BY_ID.get(template_id)
