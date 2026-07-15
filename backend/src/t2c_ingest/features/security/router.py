"""Endpoints administrativos de Segurança (checklist + visão geral)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.security import service

router = APIRouter(prefix="/security", tags=["security"])


def _guard():
    return Depends(require_permission(perms.INGEST_SECURITY_READ))


@router.get("/checklist")
def checklist(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> dict:
    return service.checklist(db)


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: CurrentUser = _guard()) -> dict:
    return service.overview(db)
