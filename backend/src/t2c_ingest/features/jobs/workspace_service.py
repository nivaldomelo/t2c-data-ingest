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

from t2c_ingest.core.config import settings
from t2c_ingest.models.job import JobDefinition

ALLOWED_EXT = {".py", ".sql", ".sh", ".json", ".yaml", ".yml", ".md", ".txt"}
BLOCKED_EXT = {".env", ".pem", ".key", ".crt", ".p12", ".jks", ".properties", ".ini", ".exe",
               ".dll", ".so", ".bin", ".jar", ".zip", ".gz", ".tar"}
MAX_BYTES = 1_000_000
_LANG = {".py": "python", ".sql": "sql", ".sh": "shell", ".json": "json", ".yaml": "yaml",
         ".yml": "yaml", ".md": "markdown", ".txt": "text"}

MAIN_TEMPLATES = {
    "spark_python": (
        'from pyspark.sql import SparkSession\n\n'
        'spark = (\n    SparkSession.builder\n    .appName("novo_job_spark")\n    .getOrCreate()\n)\n\n'
        'try:\n    print("Iniciando job Spark")\nfinally:\n    spark.stop()\n'
    ),
    "python": 'def main():\n    print("Iniciando job Python")\n\n\nif __name__ == "__main__":\n    main()\n',
}


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
    """Return the job's workspace root (realpath), guaranteed inside an allowed dir.

    Uses the script's parent dir when the script lives in an allowed dir; otherwise a per-job
    dir under JOB_WORKSPACES_DIR (auto-created with a starter main.py)."""
    if job.script_path:
        parent = os.path.realpath(os.path.dirname(job.script_path))
        if _within_allowed(parent):
            return parent
    base = os.path.realpath(settings.job_workspaces_dir)
    root = os.path.join(base, str(job.id))
    if not (_within_allowed(base) or _within_allowed(os.path.realpath(root))):
        raise WorkspaceError(500, "Diretório de workspaces não está entre os permitidos.")
    if not os.path.exists(root):
        os.makedirs(root, exist_ok=True)
        os.makedirs(os.path.join(root, "utils"), exist_ok=True)
        tmpl = MAIN_TEMPLATES.get(job.type or "", MAIN_TEMPLATES["python"])
        with open(os.path.join(root, "main.py"), "w", encoding="utf-8") as fh:
            fh.write(tmpl)
        with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as fh:
            fh.write(f"# {job.name}\n\nWorkspace de código do job.\n")
    return os.path.realpath(root)


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
def read_file(root: str, rel: str) -> dict:
    real = safe_path(root, rel, must_exist=True)
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
    backup = _backup(job_id, real, "update", rel)
    with open(real, "w", encoding="utf-8") as fh:
        fh.write(content)
    return {"action": "updated", "backup_path": backup, "hash_before": sha256(before), "hash_after": sha256(content),
            "size_before": len(before.encode()), "size_after": len(content.encode()), "last_modified_at": iso_mtime(real)}


def create_file(root: str, rel: str, content: str) -> dict:
    real = safe_path(root, rel)
    check_editable(real)
    if os.path.exists(real):
        raise WorkspaceError(409, "Já existe um arquivo com esse caminho.")
    os.makedirs(os.path.dirname(real), exist_ok=True)
    with open(real, "w", encoding="utf-8") as fh:
        fh.write(content or "")
    return {"action": "created", "hash_after": sha256(content or ""), "size_after": len((content or "").encode()), "last_modified_at": iso_mtime(real)}


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
