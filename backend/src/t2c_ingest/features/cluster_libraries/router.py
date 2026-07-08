from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.cluster_libraries import validator
from t2c_ingest.models.cluster_library import ClusterLibrary, ClusterLibraryAction
from t2c_ingest.schemas.cluster_library import (
    LibraryActionDetailOut,
    LibraryActionOut,
    LibraryDetailOut,
    LibraryInstallRequest,
    LibraryOut,
    LibrarySummary,
    PackageValidateRequest,
    PackageValidateResponse,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/libraries", tags=["cluster-libraries"])
# Actions are addressed under a separate top-level path per the spec.
actions_router = APIRouter(prefix="/library-actions", tags=["cluster-libraries"])


def _queue_action(db: Session, *, library: ClusterLibrary, action: str, spec: str, user: CurrentUser) -> ClusterLibraryAction:
    row = ClusterLibraryAction(
        library_id=library.id, cluster_id=library.cluster_id, action=action,
        package_spec=spec, status="queued", requested_by=user.email,
    )
    db.add(row)
    library.last_action_at = func.now()
    library.last_action_status = "queued"
    if action in ("install", "reinstall"):
        library.status = "queued"
    return row


@router.get("/summary", response_model=LibrarySummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_LIBRARIES_READ)),
) -> LibrarySummary:
    def count(**where) -> int:
        stmt = select(func.count(ClusterLibrary.id))
        for k, v in where.items():
            stmt = stmt.where(getattr(ClusterLibrary, k) == v)
        return db.scalar(stmt) or 0

    running = db.scalar(
        select(func.count(ClusterLibraryAction.id)).where(ClusterLibraryAction.status.in_(("queued", "running")))
    ) or 0
    last = db.scalar(
        select(ClusterLibrary.installed_at).where(ClusterLibrary.installed_at.is_not(None))
        .order_by(ClusterLibrary.installed_at.desc()).limit(1)
    )
    return LibrarySummary(
        installed=count(status="installed"),
        success=count(status="installed"),
        failed=count(status="failed"),
        running=running,
        last_installed_at=last,
    )


@router.get("", response_model=PageOut[LibraryOut])
def list_libraries(
    params: PageParams = Depends(),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_LIBRARIES_READ)),
) -> PageOut[LibraryOut]:
    stmt = select(ClusterLibrary)
    count_stmt = select(func.count(ClusterLibrary.id))
    filters = []
    if status_filter:
        filters.append(ClusterLibrary.status == status_filter)
    if search:
        filters.append(ClusterLibrary.package_name.ilike(f"%{search.strip()}%"))
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(ClusterLibrary.package_name).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([LibraryOut.model_validate(r) for r in rows], total, params)


@router.post("/validate-package", response_model=PackageValidateResponse)
def validate_package(
    payload: PackageValidateRequest,
    _: CurrentUser = Depends(require_permission(perms.INGEST_LIBRARIES_READ)),
) -> PackageValidateResponse:
    result = validator.validate_package_spec(payload.package_spec)
    return PackageValidateResponse(**result.as_dict())


@router.post("/install", response_model=LibraryDetailOut, status_code=status.HTTP_201_CREATED)
def install_library(
    payload: LibraryInstallRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_LIBRARIES_INSTALL)),
) -> LibraryDetailOut:
    raw = validator.build_spec(payload.package, payload.version, payload.package_spec)
    result = validator.validate_package_spec(raw)
    if not result.valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.error)

    # Upsert by (package_name, cluster_id).
    library = db.scalar(
        select(ClusterLibrary).where(
            ClusterLibrary.package_name == result.package_name,
            ClusterLibrary.cluster_id.is_(payload.cluster_id) if payload.cluster_id is None
            else ClusterLibrary.cluster_id == payload.cluster_id,
        )
    )
    if library is None:
        library = ClusterLibrary(
            cluster_id=payload.cluster_id, package_name=result.package_name,
            package_version=result.version, package_spec=result.normalized_spec,
            source="pypi", install_scope=payload.install_scope or "cluster",
            status="queued", note=payload.note, installed_by=user.email,
        )
        db.add(library)
        db.flush()
    else:
        library.package_version = result.version
        library.package_spec = result.normalized_spec
        library.install_scope = payload.install_scope or library.install_scope
        library.note = payload.note or library.note
        library.active = True

    _queue_action(db, library=library, action="install", spec=result.normalized_spec, user=user)
    record_audit(db, action="CLUSTER_LIBRARY_INSTALL_REQUESTED", user=user, entity_type="cluster_library",
                 entity_id=library.id, detail={"package_spec": result.normalized_spec})
    db.commit()
    db.refresh(library)
    return _detail(db, library)


@router.get("/{library_id}", response_model=LibraryDetailOut)
def get_library(
    library_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_LIBRARIES_READ)),
) -> LibraryDetailOut:
    library = db.get(ClusterLibrary, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    return _detail(db, library)


@router.post("/{library_id}/reinstall", response_model=LibraryDetailOut)
def reinstall_library(
    library_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_LIBRARIES_INSTALL)),
) -> LibraryDetailOut:
    library = db.get(ClusterLibrary, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    _queue_action(db, library=library, action="reinstall", spec=library.package_spec, user=user)
    record_audit(db, action="CLUSTER_LIBRARY_REINSTALL_REQUESTED", user=user, entity_type="cluster_library",
                 entity_id=library.id, detail={"package_spec": library.package_spec})
    db.commit()
    db.refresh(library)
    return _detail(db, library)


@router.post("/{library_id}/uninstall", response_model=LibraryDetailOut)
def uninstall_library(
    library_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_LIBRARIES_UNINSTALL)),
) -> LibraryDetailOut:
    library = db.get(ClusterLibrary, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    library.removed_by = user.email
    _queue_action(db, library=library, action="uninstall", spec=library.package_spec, user=user)
    record_audit(db, action="CLUSTER_LIBRARY_UNINSTALL_REQUESTED", user=user, entity_type="cluster_library",
                 entity_id=library.id, detail={"package_spec": library.package_spec})
    db.commit()
    db.refresh(library)
    return _detail(db, library)


@router.get("/{library_id}/actions", response_model=list[LibraryActionOut])
def library_actions(
    library_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_LIBRARIES_READ)),
) -> list[LibraryActionOut]:
    if not db.get(ClusterLibrary, library_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    rows = db.scalars(
        select(ClusterLibraryAction).where(ClusterLibraryAction.library_id == library_id)
        .order_by(ClusterLibraryAction.id.desc())
    ).all()
    return [LibraryActionOut.model_validate(r) for r in rows]


@actions_router.get("/{action_id}", response_model=LibraryActionDetailOut)
def get_action(
    action_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_LIBRARIES_READ)),
) -> LibraryActionDetailOut:
    row = db.get(ClusterLibraryAction, action_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    return LibraryActionDetailOut.model_validate(row)


@actions_router.get("/{action_id}/logs")
def get_action_logs(
    action_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_LOGS_READ)),
) -> dict:
    row = db.get(ClusterLibraryAction, action_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    return {"action_id": row.id, "status": row.status, "command_safe": row.command_safe, "logs": row.logs or ""}


def _detail(db: Session, library: ClusterLibrary) -> LibraryDetailOut:
    detail = LibraryDetailOut.model_validate(library)
    actions = db.scalars(
        select(ClusterLibraryAction).where(ClusterLibraryAction.library_id == library.id)
        .order_by(ClusterLibraryAction.id.desc()).limit(50)
    ).all()
    detail.actions = [LibraryActionOut.model_validate(a) for a in actions]
    return detail
