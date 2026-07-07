from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone

from t2c_ingest.core.config import settings

# Language badge by file extension.
_LANG_BY_EXT = {
    ".py": "python",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".txt": "text",
    ".scala": "scala",
    ".r": "r",
}

MAX_CODE_BYTES = 1_000_000  # 1 MB safety cap for the viewer/editor


class CodeError(Exception):
    """Raised when a script cannot be served/saved. ``status`` maps to an HTTP code."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def detect_language(script_path: str, job_type: str | None) -> str:
    _, ext = os.path.splitext(script_path or "")
    lang = _LANG_BY_EXT.get(ext.lower())
    if lang:
        return lang
    if job_type == "spark_sql":
        return "sql"
    if job_type in {"spark_python", "python", "spark_submit"}:
        return "python"
    return "text"


def is_editable_extension(script_path: str) -> bool:
    _, ext = os.path.splitext(script_path or "")
    ext = ext.lower()
    if ext in settings.job_code_blocked_extensions_set:
        return False
    return ext in settings.job_code_editable_extensions_set


def _validate_within_allowed(script_path: str) -> str:
    """Resolve ``script_path`` and ensure it lives inside an allowed directory.

    Blocks path traversal / absolute escapes: the realpath (symlinks resolved) must be equal to
    or nested under a configured allowed directory. Returns the safe real path.
    """
    if not script_path or not script_path.strip():
        raise CodeError(400, "Este job não possui um caminho de script definido.")

    real = os.path.realpath(script_path)
    for allowed in settings.allowed_script_dirs_list:
        allowed_real = os.path.realpath(allowed)
        if real == allowed_real or real.startswith(allowed_real + os.sep):
            return real
    raise CodeError(403, "Acesso negado: o caminho do script está fora dos diretórios permitidos.")


def _iso_mtime(real: str) -> str:
    return datetime.fromtimestamp(os.path.getmtime(real), tz=timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def file_metadata(script_path: str) -> dict:
    """Return {real_path, last_modified_at, size_bytes} after validating the path/existence."""
    real = _validate_within_allowed(script_path)
    if not os.path.exists(real):
        raise CodeError(404, "Arquivo do script não encontrado no servidor.")
    if not os.path.isfile(real):
        raise CodeError(400, "O caminho do script não aponta para um arquivo.")
    return {
        "real_path": real,
        "last_modified_at": _iso_mtime(real),
        "size_bytes": os.path.getsize(real),
    }


def read_job_code(script_path: str) -> str:
    """Return the file contents after validating the path. Raises CodeError on any problem."""
    meta = file_metadata(script_path)
    real = meta["real_path"]
    try:
        if meta["size_bytes"] > MAX_CODE_BYTES:
            raise CodeError(413, "Arquivo muito grande para exibição.")
        with open(real, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except PermissionError:
        raise CodeError(403, "O servidor não tem permissão para ler este arquivo.")
    except CodeError:
        raise
    except OSError as exc:  # noqa: BLE001
        raise CodeError(500, f"Falha ao ler o arquivo: {exc}")


def write_job_code(
    script_path: str,
    content: str,
    expected_last_modified_at: str | None,
    *,
    job_id: int,
) -> dict:
    """Validate, backup and overwrite the script. Returns metadata + backup/hash info.

    Raises CodeError: 403 (outside allowed / not editable / no OS permission), 404 (missing),
    409 (edit conflict), 400 (binary content), 413 (too large).
    """
    real = _validate_within_allowed(script_path)
    if not os.path.isfile(real):
        raise CodeError(404, "Arquivo do script não encontrado no servidor.")
    if not is_editable_extension(real):
        raise CodeError(403, "Este tipo de arquivo não pode ser editado por segurança.")
    if "\x00" in content:
        raise CodeError(400, "Conteúdo binário não é permitido.")
    if len(content.encode("utf-8", errors="replace")) > MAX_CODE_BYTES:
        raise CodeError(413, "Conteúdo excede o tamanho máximo permitido.")

    # Optimistic-lock conflict check.
    current_iso = _iso_mtime(real)
    if expected_last_modified_at and expected_last_modified_at != current_iso:
        raise CodeError(
            409,
            "Este arquivo foi alterado por outro usuário ou processo. "
            "Recarregue o código antes de salvar.",
        )

    try:
        with open(real, "r", encoding="utf-8", errors="replace") as fh:
            before = fh.read()
    except PermissionError:
        raise CodeError(403, "O servidor não tem permissão para ler este arquivo.")

    size_before = os.path.getsize(real)
    hash_before = _sha256(before)

    # Backup BEFORE overwriting.
    backup_path = _backup(real, job_id)

    try:
        with open(real, "w", encoding="utf-8") as fh:
            fh.write(content)
    except PermissionError:
        raise CodeError(403, "O servidor não tem permissão para escrever neste arquivo.")
    except OSError as exc:  # noqa: BLE001
        raise CodeError(500, f"Falha ao salvar o arquivo: {exc}")

    return {
        "real_path": real,
        "backup_path": backup_path,
        "content_hash_before": hash_before,
        "content_hash_after": _sha256(content),
        "size_before_bytes": size_before,
        "size_after_bytes": os.path.getsize(real),
        "last_modified_at": _iso_mtime(real),
    }


def _backup(real: str, job_id: int) -> str | None:
    backup_dir = settings.job_code_backup_dir
    try:
        os.makedirs(backup_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(real))[0]
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = os.path.join(backup_dir, f"{job_id}_{stem}_{ts}.bak")
        shutil.copy2(real, backup_path)
        return backup_path
    except OSError:
        # Backup dir not writable — do not block the save, but signal no backup was made.
        return None
