"""Secure per-job code workspace: a file tree scoped to an authorized directory.

All paths are resolved with realpath and confirmed to stay inside the job's workspace root,
which itself must be inside a configured allowed directory. Only a safe extension allowlist may
be created/edited; sensitive/binary extensions are blocked. Backups are taken before any
destructive change.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone

from t2c_ingest.core.config import is_dev_environment, settings
from t2c_ingest.models.job import JobDefinition

ALLOWED_EXT = {".py", ".sql", ".sh", ".json", ".yaml", ".yml", ".md", ".txt"}
BLOCKED_EXT = {".env", ".pem", ".key", ".crt", ".p12", ".jks", ".properties", ".ini", ".exe",
               ".dll", ".so", ".bin", ".jar", ".zip", ".gz", ".tar"}
MAX_BYTES = 1_000_000
_LANG = {".py": "python", ".sql": "sql", ".sh": "shell", ".json": "json", ".yaml": "yaml",
         ".yml": "yaml", ".md": "markdown", ".txt": "text"}

class WorkspaceError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _allowed_roots() -> list[str]:
    return [os.path.realpath(d) for d in settings.allowed_script_dirs_list]


def _within_allowed(real: str) -> bool:
    for root in _allowed_roots():
        if real == root or real.startswith(root + os.sep):
            return True
    return False


def resolve_workspace(job: JobDefinition) -> str:
    """Return the job's workspace root (realpath): the folder of its versioned script.

    All jobs are provisioned with a script inside a git-tracked allowed dir, so the workspace is
    that script's parent folder. Jobs without a valid versioned script cannot open a workspace."""
    if job.script_path:
        parent = os.path.realpath(os.path.dirname(job.script_path))
        if _within_allowed(parent):
            return parent
    raise WorkspaceError(
        400,
        "Este job não possui um script versionado em um diretório permitido. "
        "Defina o caminho do script (em spark/jobs ou python_jobs) antes de abrir o workspace.",
    )


def safe_path(root: str, rel_path: str | None, *, must_exist: bool = False) -> str:
    """Resolve a relative path inside root, blocking traversal/absolute escapes."""
    raw = (rel_path or "").strip()
    if raw.startswith("/") or raw.startswith("\\") or (len(raw) > 1 and raw[1] == ":"):
        raise WorkspaceError(403, "Caminhos absolutos não são permitidos.")
    rel = raw
    if ".." in rel.replace("\\", "/").split("/"):
        raise WorkspaceError(403, "Caminho inválido (path traversal não é permitido).")
    candidate = os.path.realpath(os.path.join(root, rel))
    if not (candidate == root or candidate.startswith(root + os.sep)):
        raise WorkspaceError(403, "Este arquivo está fora do workspace permitido.")
    if not _within_allowed(candidate):
        raise WorkspaceError(403, "Este arquivo está fora dos diretórios permitidos.")
    if must_exist and not os.path.exists(candidate):
        raise WorkspaceError(404, "Arquivo não encontrado.")
    return candidate


def check_editable(path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext in BLOCKED_EXT:
        raise WorkspaceError(403, "Não é permitido editar/criar este tipo de arquivo.")
    if ext not in ALLOWED_EXT:
        raise WorkspaceError(403, f"Extensão não permitida. Use uma de: {', '.join(sorted(ALLOWED_EXT))}.")


def language_for(path: str) -> str:
    return _LANG.get(os.path.splitext(path)[1].lower(), "text")


def iso_mtime(real: str) -> str:
    return datetime.fromtimestamp(os.path.getmtime(real), tz=timezone.utc).isoformat()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def build_tree(root: str) -> dict:
    def node(abs_path: str) -> dict:
        name = os.path.basename(abs_path) or "job-root"
        rel = os.path.relpath(abs_path, root)
        rel = "" if rel == "." else rel
        if os.path.isdir(abs_path):
            children = []
            for entry in sorted(os.listdir(abs_path), key=lambda e: (not os.path.isdir(os.path.join(abs_path, e)), e.lower())):
                if entry.startswith(".") or entry == "__pycache__":
                    continue
                children.append(node(os.path.join(abs_path, entry)))
            return {"name": name, "path": rel, "type": "folder", "children": children}
        return {"name": name, "path": rel, "type": "file", "language": language_for(abs_path)}
    return node(root)


def _backup(job_id: int, real: str, action: str, rel: str) -> str | None:
    try:
        bdir = os.path.join(settings.job_code_backup_dir, str(job_id))
        os.makedirs(bdir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_rel = rel.replace("/", "_").replace(".", "_")
        bpath = os.path.join(bdir, f"{ts}_{action}_{safe_rel}.bak")
        shutil.copy2(real, bpath)
        return bpath
    except OSError:
        return None


# ── operations (return metadata; router persists version + audit) ──
def check_readable(path: str) -> None:
    """Defense-in-depth: never serve secret/blocked files or dotfiles, even by direct path."""
    base = os.path.basename(path)
    if base.startswith("."):
        raise WorkspaceError(403, "Arquivos ocultos não podem ser lidos.")
    if os.path.splitext(path)[1].lower() in BLOCKED_EXT:
        raise WorkspaceError(403, "Este tipo de arquivo não pode ser lido (possível segredo).")


def read_file(root: str, rel: str) -> dict:
    real = safe_path(root, rel, must_exist=True)
    check_readable(real)
    if not os.path.isfile(real):
        raise WorkspaceError(400, "O caminho não aponta para um arquivo.")
    if os.path.getsize(real) > MAX_BYTES:
        raise WorkspaceError(413, "Arquivo muito grande para exibição.")
    try:
        with open(real, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except PermissionError:
        raise WorkspaceError(403, "O servidor não tem permissão para ler este arquivo.")
    return {"path": rel, "file_name": os.path.basename(real), "language": language_for(real),
            "content": content, "last_modified_at": iso_mtime(real), "size_bytes": os.path.getsize(real),
            "editable": os.path.splitext(real)[1].lower() in ALLOWED_EXT}


import re as _re

# Padrões de secret hardcoded no código (nomes de padrão, nunca o valor).
_SECRET_PATTERNS: list[tuple[str, "_re.Pattern"]] = [
    ("credencial_atribuida", _re.compile(
        r"(?i)\b(password|senha|passwd|pwd|secret|api[_-]?key|access[_-]?key|secret[_-]?key|"
        r"client[_-]?secret|token|authorization|bearer|aws_secret_access_key|aws_access_key_id)\b"
        r"\s*[:=]\s*[\"']?[^\s\"']{4,}")),
    ("aws_access_key_id", _re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key_block", _re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jdbc_com_senha", _re.compile(r"(?i)jdbc:[^\s\"']*password=[^\s\"'&]+")),
    ("bearer_token", _re.compile(r"(?i)Authorization\s*:\s*Bearer\s+[A-Za-z0-9._\-]{8,}")),
]


def scan_code_secrets(content: str) -> list[str]:
    """Retorna os NOMES dos padrões de secret encontrados no código (nunca os valores)."""
    if not content:
        return []
    found = []
    for name, rx in _SECRET_PATTERNS:
        if rx.search(content):
            found.append(name)
    return found


def _enforce_secret_scan(content: str, result: dict) -> dict:
    """Bloqueia (produção) ou alerta (dev) se houver secret no código. Anexa 'secret_findings'."""
    findings = scan_code_secrets(content)
    if findings:
        if not is_dev_environment(getattr(settings, "env", "production")):
            raise WorkspaceError(
                422,
                "Possível credencial no código (" + ", ".join(findings) + "). Use Origens/Variáveis "
                "secretas em vez de fixar segredos no código. Salvamento bloqueado em produção.")
        result["secret_findings"] = findings
    return result


def write_file(job_id: int, root: str, rel: str, content: str, expected_mtime: str | None) -> dict:
    real = safe_path(root, rel, must_exist=True)
    check_editable(real)
    if "\x00" in content:
        raise WorkspaceError(400, "Conteúdo binário não é permitido.")
    if len(content.encode("utf-8", errors="replace")) > MAX_BYTES:
        raise WorkspaceError(413, "Conteúdo excede o tamanho máximo.")
    if expected_mtime and expected_mtime != iso_mtime(real):
        raise WorkspaceError(409, "Este arquivo foi alterado por outro usuário ou processo. Recarregue antes de salvar.")
    with open(real, "r", encoding="utf-8", errors="replace") as fh:
        before = fh.read()
    result = {"action": "updated", "hash_before": sha256(before), "hash_after": sha256(content),
              "size_before": len(before.encode()), "size_after": len(content.encode())}
    _enforce_secret_scan(content, result)  # pode levantar (prod) antes de gravar
    backup = _backup(job_id, real, "update", rel)
    with open(real, "w", encoding="utf-8") as fh:
        fh.write(content)
    result.update({"backup_path": backup, "last_modified_at": iso_mtime(real)})
    return result


def create_file(root: str, rel: str, content: str) -> dict:
    real = safe_path(root, rel)
    check_editable(real)
    if os.path.exists(real):
        raise WorkspaceError(409, "Já existe um arquivo com esse caminho.")
    result = {"action": "created", "hash_after": sha256(content or ""), "size_after": len((content or "").encode())}
    _enforce_secret_scan(content or "", result)  # pode levantar (prod) antes de gravar
    os.makedirs(os.path.dirname(real), exist_ok=True)
    with open(real, "w", encoding="utf-8") as fh:
        fh.write(content or "")
    result["last_modified_at"] = iso_mtime(real)
    return result


def create_folder(root: str, rel: str) -> dict:
    real = safe_path(root, rel)
    if os.path.exists(real):
        raise WorkspaceError(409, "Já existe uma pasta/arquivo com esse caminho.")
    os.makedirs(real, exist_ok=False)
    return {"action": "folder_created"}


def rename(job_id: int, root: str, old_rel: str, new_rel: str) -> dict:
    old_real = safe_path(root, old_rel, must_exist=True)
    new_real = safe_path(root, new_rel)
    if old_real == root:
        raise WorkspaceError(403, "Não é permitido renomear a pasta raiz do job.")
    if os.path.exists(new_real):
        raise WorkspaceError(409, "Já existe um arquivo/pasta no destino.")
    if os.path.isfile(old_real):
        check_editable(new_real)
        _backup(job_id, old_real, "rename", old_rel)
    os.makedirs(os.path.dirname(new_real), exist_ok=True)
    os.rename(old_real, new_real)
    return {"action": "renamed"}


def delete_file(job_id: int, root: str, rel: str) -> dict:
    real = safe_path(root, rel, must_exist=True)
    if real == root:
        raise WorkspaceError(403, "Não é permitido apagar a pasta raiz do job.")
    if not os.path.isfile(real):
        raise WorkspaceError(400, "O caminho não é um arquivo.")
    backup = _backup(job_id, real, "delete", rel)
    with open(real, "r", encoding="utf-8", errors="replace") as fh:
        before = fh.read()
    os.remove(real)
    return {"action": "deleted", "backup_path": backup, "hash_before": sha256(before), "size_before": len(before.encode())}


def delete_folder(root: str, rel: str) -> dict:
    real = safe_path(root, rel, must_exist=True)
    if real == root:
        raise WorkspaceError(403, "Não é permitido apagar a pasta raiz do job.")
    if not os.path.isdir(real):
        raise WorkspaceError(400, "O caminho não é uma pasta.")
    if any(not e.startswith(".") for e in os.listdir(real)):
        raise WorkspaceError(409, "A pasta não está vazia.")
    os.rmdir(real)
    return {"action": "folder_deleted"}
