"""Endpoints administrativos da integração com o t2c_data (outbox — ponto 16).

Acompanhar e reprocessar eventos operacionais. Leitura para quem tem acesso; reprocessar exige
permissão administrativa. Payloads são expostos já mascarados (sem segredos).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.integration import outbox

router = APIRouter(prefix="/integrations/t2c-data", tags=["integrations"])


def _read():
    return Depends(require_permission(perms.INGEST_INTEGRATIONS_READ))


def _retry():
    return Depends(require_permission(perms.INGEST_INTEGRATIONS_RETRY))


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: CurrentUser = _read()) -> dict:
    return outbox.stats(db)


@router.get("/outbox")
def list_outbox(
    status: str | None = Query(None),
    event_type: str | None = Query(None),
    aggregate_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: CurrentUser = _read(),
) -> dict:
    return outbox.list_outbox(db, status=status, event_type=event_type,
                              aggregate_type=aggregate_type, page=page, page_size=page_size)


@router.get("/outbox/{row_id}")
def get_outbox(row_id: int, db: Session = Depends(get_db), _: CurrentUser = _read()) -> dict:
    row = outbox.get_outbox(db, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="Evento de integração não encontrado")
    return row


@router.post("/outbox/{row_id}/retry")
def retry_one(row_id: int, db: Session = Depends(get_db), _: CurrentUser = _retry()) -> dict:
    if not outbox.retry(db, row_id):
        raise HTTPException(status_code=404, detail="Evento inexistente ou já entregue")
    return {"ok": True, "id": row_id}


@router.post("/outbox/retry-dead")
def retry_dead(db: Session = Depends(get_db), _: CurrentUser = _retry()) -> dict:
    n = outbox.retry_dead(db)
    return {"ok": True, "requeued": n}
