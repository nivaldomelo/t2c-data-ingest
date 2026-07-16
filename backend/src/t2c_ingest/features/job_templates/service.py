"""JobTemplateService: lista templates, renderiza arquivos com o contexto e valida ausência de
secrets. Não escreve nada em disco (a gravação do workspace é feita por code_service na criação)."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from t2c_ingest.features.job_templates import catalog, context as ctx_builder
from t2c_ingest.features.job_templates.render import render
from t2c_ingest.features.jobs.code_service import detect_language

# Padrão de secret LITERAL: atribuição de credencial a uma string não-vazia entre aspas.
# (Referências via env/função — ex.: password=_conn_password(id) — NÃO são secret e não casam.)
_LITERAL_SECRET = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|aws_secret_access_key|authorization)"
    r"\s*[:=]\s*['\"][^'\"]+['\"]"
)


class TemplateError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def list_templates() -> list[dict]:
    return catalog.list_templates()


def get_template(template_id: str) -> dict:
    tpl = catalog.get_template(template_id)
    if not tpl:
        raise TemplateError(404, f"Template '{template_id}' não encontrado.")
    return tpl


def _read_tpl(tpl: dict, source_rel: str) -> str:
    path = catalog.TEMPLATES_DIR / tpl["dir"] / source_rel
    if not path.is_file():
        raise TemplateError(500, f"Arquivo de template ausente: {tpl['dir']}/{source_rel}")
    return path.read_text(encoding="utf-8")


def render_files(tpl: dict, context: dict) -> list[dict]:
    """Renderiza todos os arquivos do template. Recusa (422) se algum conteúdo tiver secret literal."""
    files: list[dict] = []
    for f in tpl["files"]:
        content = render(_read_tpl(tpl, f["source"]), context)
        # Guard contra secret LITERAL no conteúdo renderizado. Referências via env/função
        # (ex.: .option("password", _conn_password(id))) são permitidas — o worker resolve.
        if _LITERAL_SECRET.search(content):
            raise TemplateError(
                422, f"Template gerou conteúdo com credencial literal em {f['target']}. "
                     "Use Origens/variáveis resolvidas em runtime, não valores fixos.")
        files.append({
            "path": f["target"],
            "language": detect_language(f["target"], None),
            "content": content,
        })
    return files


def build_context(db: Session, tpl: dict, job_meta: dict, control_id: int | None) -> dict:
    return ctx_builder.build_context(db, tpl, job_meta, control_id)


def preview(db: Session, template_id: str, job_meta: dict, control_id: int | None) -> list[dict]:
    tpl = get_template(template_id)
    return render_files(tpl, build_context(db, tpl, job_meta, control_id))
