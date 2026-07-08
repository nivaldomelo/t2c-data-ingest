from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.jobs import workspace_service as ws
from t2c_ingest.models.job import JobDefinition
from t2c_ingest.models.job_code_version import JobCodeVersion
from t2c_ingest.schemas.workspace import (
    WorkspaceCreateFile,
    WorkspaceFileOut,
    WorkspaceOpResult,
    WorkspacePathRequest,
    WorkspaceRenameRequest,
    WorkspaceSaveRequest,
    WorkspaceTree,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/jobs", tags=["jobs-workspace"])

_AUDIT = {
    "created": "JOB_CODE_FILE_CREATED", "updated": "JOB_CODE_FILE_UPDATED",
    "renamed": "JOB_CODE_FILE_RENAMED", "deleted": "JOB_CODE_FILE_DELETED",
    "folder_created": "JOB_CODE_FOLDER_CREATED", "folder_deleted": "JOB_CODE_FOLDER_DELETED",
}


def _job(db: Session, job_id: int) -> JobDefinition:
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este job foi excluído. O código foi arquivado e o workspace não está disponível.",
        )
    return job


def _record(db: Session, job: JobDefinition, user: CurrentUser, info: dict, file_path: str) -> None:
    action = info.get("action", "updated")
    db.add(JobCodeVersion(
        job_id=job.id, script_path=job.script_path or "", action=action, file_path=file_path,
        backup_path=info.get("backup_path"), content_hash_before=info.get("hash_before"),
        content_hash_after=info.get("hash_after"), changed_by=user.email,
        size_before_bytes=info.get("size_before"), size_after_bytes=info.get("size_after"),
    ))
    record_audit(db, action=_AUDIT.get(action, "JOB_CODE_FILE_UPDATED"), user=user, entity_type="job",
                 entity_id=job.id, detail={"file_path": file_path, "backup_path": info.get("backup_path")})
    db.commit()


def _handle(fn):
    try:
        return fn()
    except ws.WorkspaceError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


@router.get("/{job_id}/workspace/tree", response_model=WorkspaceTree)
def workspace_tree(
    job_id: int, db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_READ)),
) -> WorkspaceTree:
    job = _job(db, job_id)
    root = _handle(lambda: ws.resolve_workspace(job))
    record_audit(db, action="JOB_WORKSPACE_OPENED", user=user, entity_type="job", entity_id=job.id)
    db.commit()
    main_rel = None
    if job.script_path:
        import os
        real = os.path.realpath(job.script_path)
        if real.startswith(root + os.sep) or real == root:
            main_rel = os.path.relpath(real, root)
    return WorkspaceTree(job_id=job.id, workspace_path=root, main_path=main_rel,
                         editable=user.has(perms.INGEST_JOBS_CODE_WRITE), tree=_handle(lambda: ws.build_tree(root)))


@router.get("/{job_id}/workspace/file", response_model=WorkspaceFileOut)
def workspace_read(
    job_id: int, path: str = Query(...), db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_READ)),
) -> WorkspaceFileOut:
    job = _job(db, job_id)
    root = _handle(lambda: ws.resolve_workspace(job))
    data = _handle(lambda: ws.read_file(root, path))
    editable = data.pop("editable") and user.has(perms.INGEST_JOBS_CODE_WRITE)
    return WorkspaceFileOut(job_id=job.id, **data, editable=editable)


@router.put("/{job_id}/workspace/file", response_model=WorkspaceFileOut)
def workspace_save(
    job_id: int, payload: WorkspaceSaveRequest, db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_WRITE)),
) -> WorkspaceFileOut:
    job = _job(db, job_id)
    root = _handle(lambda: ws.resolve_workspace(job))
    info = _handle(lambda: ws.write_file(job.id, root, payload.path, payload.content, payload.expected_last_modified_at))
    _record(db, job, user, info, payload.path)
    data = _handle(lambda: ws.read_file(root, payload.path))
    data.pop("editable", None)
    return WorkspaceFileOut(job_id=job.id, **data, editable=True)


@router.post("/{job_id}/workspace/file", response_model=WorkspaceOpResult, status_code=status.HTTP_201_CREATED)
def workspace_create_file(
    job_id: int, payload: WorkspaceCreateFile, db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_CREATE)),
) -> WorkspaceOpResult:
    job = _job(db, job_id)
    root = _handle(lambda: ws.resolve_workspace(job))
    info = _handle(lambda: ws.create_file(root, payload.path, payload.content))
    _record(db, job, user, info, payload.path)
    return WorkspaceOpResult(action="created", path=payload.path, last_modified_at=info.get("last_modified_at"))


@router.post("/{job_id}/workspace/folder", response_model=WorkspaceOpResult, status_code=status.HTTP_201_CREATED)
def workspace_create_folder(
    job_id: int, payload: WorkspacePathRequest, db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_CREATE)),
) -> WorkspaceOpResult:
    job = _job(db, job_id)
    root = _handle(lambda: ws.resolve_workspace(job))
    info = _handle(lambda: ws.create_folder(root, payload.path))
    _record(db, job, user, info, payload.path)
    return WorkspaceOpResult(action="folder_created", path=payload.path)


@router.put("/{job_id}/workspace/rename", response_model=WorkspaceOpResult)
def workspace_rename(
    job_id: int, payload: WorkspaceRenameRequest, db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_RENAME)),
) -> WorkspaceOpResult:
    job = _job(db, job_id)
    root = _handle(lambda: ws.resolve_workspace(job))
    info = _handle(lambda: ws.rename(job.id, root, payload.old_path, payload.new_path))
    _record(db, job, user, info, f"{payload.old_path} -> {payload.new_path}")
    return WorkspaceOpResult(action="renamed", path=payload.new_path)


@router.delete("/{job_id}/workspace/file", status_code=status.HTTP_200_OK, response_model=WorkspaceOpResult)
def workspace_delete_file(
    job_id: int, path: str = Query(...), db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_DELETE)),
) -> WorkspaceOpResult:
    job = _job(db, job_id)
    root = _handle(lambda: ws.resolve_workspace(job))
    info = _handle(lambda: ws.delete_file(job.id, root, path))
    _record(db, job, user, info, path)
    return WorkspaceOpResult(action="deleted", path=path)


@router.delete("/{job_id}/workspace/folder", status_code=status.HTTP_200_OK, response_model=WorkspaceOpResult)
def workspace_delete_folder(
    job_id: int, path: str = Query(...), db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_JOBS_CODE_DELETE)),
) -> WorkspaceOpResult:
    job = _job(db, job_id)
    root = _handle(lambda: ws.resolve_workspace(job))
    info = _handle(lambda: ws.delete_folder(root, path))
    _record(db, job, user, info, path)
    return WorkspaceOpResult(action="folder_deleted", path=path)
