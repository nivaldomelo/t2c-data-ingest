from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.destinations import resolver, service
from t2c_ingest.features.destinations.schemas import (
    DestinationCreate,
    DestinationOut,
    DestinationSummary,
    DestinationTestResult,
    DestinationUpdate,
)
from t2c_ingest.models.connection import Connection
from t2c_ingest.models.destination import Destination
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/destinations", tags=["destinations"])


def _to_out(db: Session, dest: Destination) -> DestinationOut:
    conn = db.get(Connection, dest.connection_id)
    out = DestinationOut.model_validate(dest)
    out.connection_name = conn.name if conn else None
    out.connection_type = conn.connection_type if conn else None
    out.target_display = resolver.target_display(dest)
    return out


def _active_q():
    return Destination.deleted_at.is_(None)


@router.get("/summary", response_model=DestinationSummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DESTINATIONS_READ)),
) -> DestinationSummary:
    def _count(*where) -> int:
        stmt = select(func.count(Destination.id)).where(_active_q())
        for w in where:
            stmt = stmt.where(w)
        return db.scalar(stmt) or 0

    return DestinationSummary(
        total=_count(),
        postgres=_count(Destination.destination_type == "postgres"),
        s3=_count(Destination.destination_type == "s3"),
        active=_count(Destination.active.is_(True)),
        test_failed=_count(Destination.last_test_status == "failed"),
    )


@router.get("", response_model=PageOut[DestinationOut])
def list_destinations(
    params: PageParams = Depends(),
    destination_type: str | None = None,
    connection_id: int | None = None,
    active: bool | None = None,
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DESTINATIONS_READ)),
) -> PageOut[DestinationOut]:
    stmt = select(Destination).where(_active_q())
    count_stmt = select(func.count(Destination.id)).where(_active_q())
    filters = []
    if destination_type:
        filters.append(Destination.destination_type == destination_type)
    if connection_id:
        filters.append(Destination.connection_id == connection_id)
    if active is not None:
        filters.append(Destination.active == active)
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(Destination.name.ilike(like), Destination.target_table.ilike(like),
                           Destination.target_bucket.ilike(like)))
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Destination.name).offset(params.offset).limit(params.limit)).all()
    return PageOut.build([_to_out(db, r) for r in rows], total, params)


@router.post("", response_model=DestinationOut, status_code=status.HTTP_201_CREATED)
def create_destination(
    payload: DestinationCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_DESTINATIONS_CREATE)),
) -> DestinationOut:
    if service.name_in_use(db, payload.name):
        raise HTTPException(status_code=409, detail="Já existe um destino com esse nome.")
    conn = service.get_connection(db, payload.connection_id)
    try:
        service.validate(payload.model_dump(), conn)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    dest = Destination(**payload.model_dump(), created_by=user.email, updated_by=user.email)
    db.add(dest)
    db.flush()
    record_audit(db, action="DESTINATION_CREATED", user=user, entity_type="destination",
                 entity_id=dest.id, detail={"type": dest.destination_type, "connection_id": dest.connection_id})
    db.commit()
    db.refresh(dest)
    return _to_out(db, dest)


def _require(db: Session, destination_id: int) -> Destination:
    dest = db.get(Destination, destination_id)
    if not dest or dest.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Destino não encontrado")
    return dest


@router.get("/{destination_id}", response_model=DestinationOut)
def get_destination(
    destination_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DESTINATIONS_READ)),
) -> DestinationOut:
    return _to_out(db, _require(db, destination_id))


@router.put("/{destination_id}", response_model=DestinationOut)
def update_destination(
    destination_id: int,
    payload: DestinationUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_DESTINATIONS_WRITE)),
) -> DestinationOut:
    dest = _require(db, destination_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and service.name_in_use(db, data["name"], exclude_id=dest.id):
        raise HTTPException(status_code=409, detail="Já existe um destino com esse nome.")
    for key, value in data.items():
        setattr(dest, key, value)
    conn = service.get_connection(db, dest.connection_id)
    try:
        service.validate(_merged(dest), conn)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    dest.updated_by = user.email
    record_audit(db, action="DESTINATION_UPDATED", user=user, entity_type="destination", entity_id=dest.id)
    db.commit()
    db.refresh(dest)
    return _to_out(db, dest)


def _merged(dest: Destination) -> dict:
    return {c.name: getattr(dest, c.name) for c in dest.__table__.columns}


@router.delete("/{destination_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_destination(
    destination_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_DESTINATIONS_DELETE)),
) -> None:
    dest = _require(db, destination_id)
    dest.deleted_at = datetime.now(timezone.utc)
    dest.deleted_by = user.email
    dest.active = False
    record_audit(db, action="DESTINATION_DELETED", user=user, entity_type="destination", entity_id=dest.id)
    db.commit()


@router.post("/{destination_id}/test", response_model=DestinationTestResult)
def test_destination(
    destination_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_DESTINATIONS_TEST)),
) -> DestinationTestResult:
    dest = _require(db, destination_id)
    record_audit(db, action="DESTINATION_TEST_STARTED", user=user, entity_type="destination", entity_id=dest.id)
    result = service.test_destination(db, dest)
    now = datetime.now(timezone.utc)
    dest.last_test_status = result["status"]
    dest.last_test_message = result["message"]
    dest.last_tested_at = now
    record_audit(db, action="DESTINATION_TEST_SUCCEEDED" if result["status"] == "success" else "DESTINATION_TEST_FAILED",
                 user=user, entity_type="destination", entity_id=dest.id, detail={"status": result["status"]})
    db.commit()
    return DestinationTestResult(status=result["status"], message=result["message"],
                                 checks=result.get("checks", []), tested_at=now)


@router.get("/{destination_id}/resolved")
def resolved(
    destination_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DESTINATIONS_READ)),
) -> dict:
    """Config normalizada (sem segredos) — usada pela UI e por integrações."""
    dest = _require(db, destination_id)
    conn = db.get(Connection, dest.connection_id)
    return resolver.normalized(dest, conn)
