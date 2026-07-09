from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.cluster_libraries import validator
from t2c_ingest.features.runtime import service
from t2c_ingest.models.runtime import RuntimeBuild, RuntimeLibrary, RuntimeValidation
from t2c_ingest.schemas.runtime import (
    RequirementsOut,
    RuntimeBuildDetailOut,
    RuntimeBuildOut,
    RuntimeLibraryIn,
    RuntimeLibraryOut,
    RuntimeLibraryUpdate,
    RuntimeSummary,
    RuntimeValidateRequest,
    RuntimeValidationDetailOut,
    RuntimeValidationOut,
)
from t2c_ingest.core.config import settings
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/summary", response_model=RuntimeSummary)
def summary(db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_READ))) -> RuntimeSummary:
    active_libs = db.scalar(select(func.count(RuntimeLibrary.id)).where(RuntimeLibrary.active.is_(True))) or 0
    active_build = db.scalar(select(RuntimeBuild.image_full_name).where(RuntimeBuild.is_active.is_(True)).limit(1))
    last_val = db.scalar(select(RuntimeValidation).order_by(RuntimeValidation.id.desc()).limit(1))
    return RuntimeSummary(
        active_libraries=active_libs,
        active_build=active_build,
        workers_expected=settings.spark_expected_workers,
        last_validation_status=last_val.status if last_val else None,
        last_validation_at=last_val.finished_at if last_val else None,
    )


# ── libraries manifest ──
@router.get("/libraries", response_model=list[RuntimeLibraryOut])
def list_libraries(db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_READ))) -> list[RuntimeLibraryOut]:
    rows = db.scalars(select(RuntimeLibrary).order_by(RuntimeLibrary.package_name)).all()
    return [RuntimeLibraryOut.model_validate(r) for r in rows]


@router.post("/libraries", response_model=RuntimeLibraryOut, status_code=status.HTTP_201_CREATED)
def add_library(payload: RuntimeLibraryIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_LIBRARIES_WRITE))) -> RuntimeLibraryOut:
    raw = validator.build_spec(payload.package, payload.version, payload.package_spec)
    result = validator.validate_package_spec(raw)
    if not result.valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.error)
    existing = db.scalar(select(RuntimeLibrary).where(RuntimeLibrary.package_name == result.package_name))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Biblioteca já cadastrada no runtime.")
    lib = RuntimeLibrary(
        package_name=result.package_name, package_version=result.version,
        package_spec=result.normalized_spec, source="pypi", active=payload.active,
        note=payload.note, created_by=user.email,
    )
    db.add(lib)
    record_audit(db, action="RUNTIME_LIBRARY_ADDED", user=user, entity_type="runtime_library", entity_id=result.package_name, detail={"spec": result.normalized_spec})
    db.commit()
    db.refresh(lib)
    return RuntimeLibraryOut.model_validate(lib)


@router.patch("/libraries/{library_id}", response_model=RuntimeLibraryOut)
def update_library(library_id: int, payload: RuntimeLibraryUpdate, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_LIBRARIES_WRITE))) -> RuntimeLibraryOut:
    lib = db.get(RuntimeLibrary, library_id)
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Biblioteca não encontrada")
    if payload.package_spec is not None:
        result = validator.validate_package_spec(payload.package_spec)
        if not result.valid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.error)
        lib.package_spec = result.normalized_spec
        lib.package_version = result.version
        lib.package_name = result.package_name
    if payload.active is not None:
        lib.active = payload.active
    if payload.note is not None:
        lib.note = payload.note
    lib.updated_by = user.email
    record_audit(db, action="RUNTIME_LIBRARY_UPDATED", user=user, entity_type="runtime_library", entity_id=lib.package_name)
    db.commit()
    db.refresh(lib)
    return RuntimeLibraryOut.model_validate(lib)


@router.delete("/libraries/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_library(library_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_LIBRARIES_WRITE))) -> None:
    lib = db.get(RuntimeLibrary, library_id)
    if not lib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Biblioteca não encontrada")
    name = lib.package_name
    db.delete(lib)
    record_audit(db, action="RUNTIME_LIBRARY_REMOVED", user=user, entity_type="runtime_library", entity_id=name)
    db.commit()


@router.get("/requirements", response_model=RequirementsOut)
def requirements(db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_READ))) -> RequirementsOut:
    content = service.generate_requirements(db)
    count = db.scalar(select(func.count(RuntimeLibrary.id)).where(RuntimeLibrary.active.is_(True))) or 0
    return RequirementsOut(content=content, library_count=count)


# ── builds ──
@router.get("/builds", response_model=list[RuntimeBuildOut])
def list_builds(db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_READ))) -> list[RuntimeBuildOut]:
    rows = db.scalars(select(RuntimeBuild).order_by(RuntimeBuild.id.desc()).limit(100)).all()
    return [RuntimeBuildOut.model_validate(r) for r in rows]


@router.get("/builds/{build_id}", response_model=RuntimeBuildDetailOut)
def get_build(build_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_READ))) -> RuntimeBuildDetailOut:
    build = db.get(RuntimeBuild, build_id)
    if not build:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Build não encontrado")
    return RuntimeBuildDetailOut.model_validate(build)


@router.post("/builds", response_model=RuntimeBuildDetailOut, status_code=status.HTTP_201_CREATED)
def create_build(db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_BUILD))) -> RuntimeBuildDetailOut:
    version = datetime.now(timezone.utc).strftime("%Y%m%d.%H%M%S")
    image = settings.runtime_image_name
    build = RuntimeBuild(
        build_version=version, image_name=image, image_tag=version,
        image_full_name=f"{image}:{version}", status="queued",
        requirements_snapshot=service.generate_requirements(db), created_by=user.email,
    )
    db.add(build)
    record_audit(db, action="RUNTIME_BUILD_REQUESTED", user=user, entity_type="runtime", entity_id=version)
    db.commit()
    db.refresh(build)
    return RuntimeBuildDetailOut.model_validate(build)


@router.post("/builds/{build_id}/activate", response_model=RuntimeBuildOut)
def activate(build_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_ACTIVATE))) -> RuntimeBuildOut:
    build = db.get(RuntimeBuild, build_id)
    if not build:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Build não encontrado")
    if build.status not in ("success", "active", "deprecated"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Só é possível ativar um build concluído com sucesso.")
    build.created_by = build.created_by or user.email
    service.activate_build(db, build)
    db.refresh(build)
    return RuntimeBuildOut.model_validate(build)


# ── validations ──
@router.get("/validations", response_model=list[RuntimeValidationOut])
def list_validations(db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_READ))) -> list[RuntimeValidationOut]:
    rows = db.scalars(select(RuntimeValidation).order_by(RuntimeValidation.id.desc()).limit(50)).all()
    return [RuntimeValidationOut.model_validate(r) for r in rows]


@router.get("/validations/{validation_id}", response_model=RuntimeValidationDetailOut)
def get_validation(validation_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_READ))) -> RuntimeValidationDetailOut:
    val = db.get(RuntimeValidation, validation_id)
    if not val:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validação não encontrada")
    return RuntimeValidationDetailOut.model_validate(val)


@router.post("/validations", response_model=RuntimeValidationOut, status_code=status.HTTP_201_CREATED)
def create_validation(payload: RuntimeValidateRequest, db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_VALIDATE))) -> RuntimeValidationOut:
    if payload.validation_type not in ("distributed", "libraries"):
        raise HTTPException(status_code=422, detail="Tipo de validação inválido.")
    libs = None
    if payload.validation_type == "libraries":
        libs = [l.package_name for l in db.scalars(select(RuntimeLibrary).where(RuntimeLibrary.active.is_(True))).all()]
    val = RuntimeValidation(
        runtime_build_id=payload.runtime_build_id, validation_type=payload.validation_type,
        status="queued", worker_count_expected=settings.spark_expected_workers,
        libraries_checked=libs, created_by=user.email,
    )
    db.add(val)
    db.commit()
    db.refresh(val)
    return RuntimeValidationOut.model_validate(val)


@router.post("/apply", response_model=RuntimeValidationOut, status_code=status.HTTP_201_CREATED)
def apply_active_image(db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission(perms.INGEST_RUNTIME_ACTIVATE))) -> RuntimeValidationOut:
    """Deploy the ACTIVE runtime image to the local Spark workers, then validate libraries.

    Recreates the worker containers with the active image (retag → recreate) and runs the
    library validation across the fresh cluster — closing the loop locally.
    """
    build = db.scalar(select(RuntimeBuild).where(RuntimeBuild.is_active.is_(True)).limit(1))
    if build is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nenhuma imagem runtime ativa. Ative um build antes de aplicar.")
    libs = [l.package_name for l in db.scalars(select(RuntimeLibrary).where(RuntimeLibrary.active.is_(True))).all()]
    val = RuntimeValidation(
        runtime_build_id=build.id, validation_type="apply", status="queued",
        worker_count_expected=settings.spark_expected_workers, libraries_checked=libs, created_by=user.email,
    )
    db.add(val)
    record_audit(db, action="RUNTIME_BUILD_ACTIVATED", user=user, entity_type="runtime", entity_id=str(build.id), detail={"apply": True})
    db.commit()
    db.refresh(val)
    return RuntimeValidationOut.model_validate(val)
