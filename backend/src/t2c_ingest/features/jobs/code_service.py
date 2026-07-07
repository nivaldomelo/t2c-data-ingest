from __future__ import annotations

import os

from t2c_ingest.core.config import settings

# Language badge by file extension.
_LANG_BY_EXT = {
    ".py": "python",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".scala": "scala",
    ".r": "r",
}

MAX_CODE_BYTES = 1_000_000  # 1 MB safety cap for the viewer


class CodeError(Exception):
    """Raised when a script cannot be served. ``status`` maps to an HTTP code."""

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
    raise CodeError(
        403,
        "Acesso negado: o caminho do script está fora dos diretórios permitidos.",
    )


def read_job_code(script_path: str) -> str:
    """Return the file contents after validating the path. Raises CodeError on any problem."""
    real = _validate_within_allowed(script_path)

    if not os.path.exists(real):
        raise CodeError(404, "Arquivo do script não encontrado no servidor.")
    if not os.path.isfile(real):
        raise CodeError(400, "O caminho do script não aponta para um arquivo.")

    try:
        size = os.path.getsize(real)
        if size > MAX_CODE_BYTES:
            raise CodeError(413, "Arquivo muito grande para exibição.")
        with open(real, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except PermissionError:
        raise CodeError(403, "O servidor não tem permissão para ler este arquivo.")
    except CodeError:
        raise
    except OSError as exc:  # noqa: BLE001
        raise CodeError(500, f"Falha ao ler o arquivo: {exc}")
