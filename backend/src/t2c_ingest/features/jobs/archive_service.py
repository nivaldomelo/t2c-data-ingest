"""Archive a job's code before soft-deleting it — code is never hard-deleted.

Flow (safe by construction): resolve the job's versioned workspace → validate it is inside an
allowed dir → COPY it into the archive dir → validate the copy → write metadata/README → only
then remove the original folder (guarded). If any step before the copy-validation fails, nothing
is removed and the caller must abort the delete.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone

from t2c_ingest.core.config import settings
from t2c_ingest.features.jobs import workspace_service as ws
from t2c_ingest.features.jobs.code_service import _slugify
from t2c_ingest.models.job import JobDefinition

README_TEXT = (
    "# Código de job arquivado — T2C Data Ingest\n\n"
    "Este código pertence a um job **excluído** do T2C Data Ingest.\n"
    "O conteúdo foi arquivado automaticamente antes da exclusão lógica (soft delete) do job.\n\n"
    "O diretório `workspace/` contém todos os arquivos de código do job no momento da exclusão.\n"
    "Consulte `metadata.json` para detalhes (job, autor e data da exclusão).\n"
)


class ArchiveError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _count_files(root: str) -> int:
    n = 0
    for _dirpath, _dirnames, filenames in os.walk(root):
        n += len(filenames)
    return n


def _skipped(reason: str) -> dict:
    """Result when there is no code to archive — the delete proceeds without archiving."""
    return {
        "skipped": True,
        "skip_reason": reason,
        "archived_code_path": None,
        "archived_workspace_path": None,
        "original_workspace_path": None,
        "original_removed": False,
        "file_count": 0,
    }


def _is_safely_removable(real: str) -> bool:
    """True only if ``real`` is strictly nested under an allowed root (never a root itself)."""
    roots = ws._allowed_roots()  # realpath'd allowed dirs
    if real in roots:
        return False
    return any(real.startswith(root + os.sep) for root in roots)


def archive_job_code(job: JobDefinition, *, deleted_by: str, now: datetime | None = None) -> dict:
    """Copy the job's workspace into the archive dir, verify, then remove the original.

    Returns a dict with archive paths and stats. Raises ArchiveError on any problem BEFORE the
    original is touched, so the caller can abort the delete without losing code.
    """
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")

    # 1) Identify the source workspace. A job may legitimately have NO code to archive (script
    # baked in the image, legacy job, or workspace never materialized on this host). That is not a
    # failure — there is nothing to lose — so we SKIP archival and let the delete proceed. We only
    # raise (and thus abort the delete) when code EXISTS but cannot be safely archived (copy/verify
    # failures below), so real code is never lost.
    try:
        source = ws.resolve_workspace(job)
    except ws.WorkspaceError:
        return _skipped("no_workspace")
    source = os.path.realpath(source)
    if not os.path.isdir(source):
        return _skipped("workspace_missing")
    if not ws._within_allowed(source):
        raise ArchiveError(403, "Workspace do job está fora dos diretórios permitidos.")

    # 2) Build the archive destination inside the (allowed) archive dir.
    archive_base = os.path.realpath(settings.job_archive_dir)
    slug = _slugify(job.name)
    dest_dir = os.path.join(archive_base, "deleted_jobs", f"{job.id}_{slug}_{ts}")
    dest_workspace = os.path.join(dest_dir, "workspace")
    if not ws._within_allowed(os.path.realpath(archive_base)):
        raise ArchiveError(500, "Diretório de archive não está entre os permitidos.")

    # 3) COPY first (never move) so a failure cannot lose code.
    try:
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copytree(source, dest_workspace, dirs_exist_ok=True)
    except OSError as exc:
        raise ArchiveError(500, f"Falha ao copiar o código para o archive: {exc}") from exc

    # 4) Validate the copy (same number of files).
    src_count, dst_count = _count_files(source), _count_files(dest_workspace)
    if dst_count < src_count:
        raise ArchiveError(500, "Verificação do archive falhou (arquivos faltando na cópia).")

    # 5) Metadata + README (no file contents are stored here beyond the copied workspace).
    metadata = {
        "job_id": job.id,
        "job_name": job.name,
        "job_type": job.type,
        "script_path": job.script_path,
        "deleted_by": deleted_by,
        "deleted_at": (now or datetime.now(timezone.utc)).isoformat(),
        "original_workspace_path": source,
        "archived_workspace_path": os.path.realpath(dest_workspace),
        "file_count": dst_count,
    }
    with open(os.path.join(dest_dir, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(dest_dir, "README_ARCHIVE.md"), "w", encoding="utf-8") as fh:
        fh.write(README_TEXT)

    # 6) Only now remove the original — guarded so we never delete an allowed root itself.
    original_removed = False
    if _is_safely_removable(source):
        try:
            shutil.rmtree(source)
            original_removed = True
        except OSError:
            # Non-fatal: the code is already safely archived. Keep going with the soft delete.
            original_removed = False

    return {
        "archived_code_path": os.path.realpath(dest_dir),
        "archived_workspace_path": os.path.realpath(dest_workspace),
        "original_workspace_path": source,
        "original_removed": original_removed,
        "file_count": dst_count,
    }
