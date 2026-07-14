from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.observability import service

router = APIRouter(prefix="/observability", tags=["observability"])


def _guard():
    return Depends(require_permission(perms.INGEST_READ))


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> dict:
    return service.overview(db)


@router.get("/today")
def today(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> list[dict]:
    return service.today(db)


@router.get("/running")
def running(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> list[dict]:
    return service.running(db)


@router.get("/failures")
def failures(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> list[dict]:
    return service.failures(db)


@router.get("/late-loads")
def late_loads(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> list[dict]:
    return service.late_loads(db)


@router.get("/sla")
def sla(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> list[dict]:
    return service.sla_breaches(db)


@router.get("/zero-records")
def zero_records(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> list[dict]:
    return service.zero_records(db)


@router.get("/watermark-stalled")
def watermark_stalled(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> list[dict]:
    return service.watermark_stalled(db)


@router.get("/source-target-failures")
def source_target_failures(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> dict:
    return service.source_target_failures(db)


@router.get("/duration-anomalies")
def duration_anomalies(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> list[dict]:
    return service.duration_anomalies(db)
