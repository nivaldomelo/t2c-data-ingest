from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.auth_bridge import permissions as perms
from pydantic import BaseModel

from t2c_ingest.features.ingestion_control import destinations_service as icd
from t2c_ingest.features.ingestion_control import resolvers
from t2c_ingest.features.ingestion_control.models import IngestionControl
from t2c_ingest.features.ingestion_control.schemas import (
    IngestionControlCreate,
    IngestionControlOut,
    IngestionControlSummary,
    IngestionControlUpdate,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/ingestion-control", tags=["ingestion_control"])


def _to_out(db: Session, row: IngestionControl) -> IngestionControlOut:
    out = IngestionControlOut.model_validate(row)
    out.source = resolvers.resolve_source(db, row)
    out.target = resolvers.resolve_target(db, row)
    return out


def _naive_now() -> datetime:
    # The controle table uses `timestamp` (no tz); store naive UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get(db: Session, control_id: int) -> IngestionControl:
    row = db.get(IngestionControl, control_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de controle não encontrado")
    return row


def _snapshot(row: IngestionControl) -> dict:
    return {
        c.name: getattr(row, c.name) for c in IngestionControl.__table__.columns  # type: ignore[attr-defined]
    }


@router.get("/summary", response_model=IngestionControlSummary)
def summary(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_READ)),
) -> IngestionControlSummary:
    def _count(*where) -> int:
        stmt = select(func.count(IngestionControl.id))
        for w in where:
            stmt = stmt.where(w)
        return db.scalar(stmt) or 0

    return IngestionControlSummary(
        total=_count(),
        ativas=_count(IngestionControl.ativo.is_(True)),
        inativas=_count(or_(IngestionControl.ativo.is_(False), IngestionControl.ativo.is_(None))),
        incrementais=_count(IngestionControl.tipo_ingestao == "INCREMENTAL"),
        ultimas_com_erro=_count(IngestionControl.status == "ERRO"),
    )


@router.get("/health")
def health(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_READ)),
) -> list[dict]:
    """Saúde por carga (atraso/SLA/zero-records/watermark parado/última qualidade)."""
    from t2c_ingest.features.observability import service as obs
    return obs.control_health(db)


@router.get("/sla")
def sla(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_READ)),
) -> dict:
    from t2c_ingest.features.observability import service as obs
    return obs.sla_report(db)


@router.get("", response_model=PageOut[IngestionControlOut])
def list_control(
    params: PageParams = Depends(),
    nome_tabela: str | None = None,
    grupo: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    ativo: bool | None = None,
    tipo_tabela: str | None = None,
    origem: str | None = None,
    destino: str | None = None,
    tipo_ingestao: str | None = None,
    origem_id: str | None = None,
    q: str | None = Query(None, description="Busca em nome_tabela/grupo/origem/destino/observacao"),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_READ)),
) -> PageOut[IngestionControlOut]:
    filters = []
    if nome_tabela:
        filters.append(IngestionControl.nome_tabela.ilike(f"%{nome_tabela}%"))
    if grupo:
        filters.append(IngestionControl.grupo == grupo)
    if status_filter:
        filters.append(IngestionControl.status == status_filter)
    if ativo is not None:
        filters.append(IngestionControl.ativo.is_(ativo))
    if tipo_tabela:
        filters.append(IngestionControl.tipo_tabela == tipo_tabela)
    if origem:
        filters.append(IngestionControl.origem == origem)
    if destino:
        filters.append(IngestionControl.destino == destino)
    if tipo_ingestao:
        filters.append(IngestionControl.tipo_ingestao == tipo_ingestao)
    if origem_id:
        filters.append(IngestionControl.origem_id == origem_id)
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                IngestionControl.nome_tabela.ilike(like),
                IngestionControl.grupo.ilike(like),
                IngestionControl.origem.ilike(like),
                IngestionControl.destino.ilike(like),
                IngestionControl.observacao.ilike(like),
            )
        )
    stmt = select(IngestionControl)
    count_stmt = select(func.count(IngestionControl.id))
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(IngestionControl.nome_tabela).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([_to_out(db, r) for r in rows], total, params)


@router.post("", response_model=IngestionControlOut, status_code=status.HTTP_201_CREATED)
def create_control(
    payload: IngestionControlCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_WRITE)),
) -> IngestionControlOut:
    now = _naive_now()
    data = payload.model_dump()
    if data.get("ativo") is None:
        data["ativo"] = True
    row = IngestionControl(**data, criado_em=now, atualizado_em=now)
    db.add(row)
    db.flush()
    record_audit(db, action="INGESTION_CONTROL_CREATED", user=user, entity_type="ingestion_control",
                 entity_id=row.id, detail={"nome_tabela": row.nome_tabela})
    db.commit()
    db.refresh(row)
    return _to_out(db, row)


@router.get("/{control_id}", response_model=IngestionControlOut)
def get_control(
    control_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_READ)),
) -> IngestionControlOut:
    return _to_out(db, _get(db, control_id))


@router.get("/{control_id}/resolved")
def resolved(
    control_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_READ)),
) -> dict:
    """Origem/destino resolvidos declarativamente (sem segredos). Usado pela UI e por jobs."""
    row = _get(db, control_id)
    return {"source": resolvers.resolve_source(db, row), "target": resolvers.resolve_target(db, row)}


@router.put("/{control_id}", response_model=IngestionControlOut)
def update_control(
    control_id: int,
    payload: IngestionControlUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_WRITE)),
) -> IngestionControlOut:
    row = _get(db, control_id)
    before = _snapshot(row)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.atualizado_em = _naive_now()
    record_audit(db, action="INGESTION_CONTROL_UPDATED", user=user, entity_type="ingestion_control",
                 entity_id=row.id, detail={"before": {"status": before.get("status"), "ativo": before.get("ativo")}})
    db.commit()
    db.refresh(row)
    return _to_out(db, row)


@router.delete("/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_control(
    control_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_DELETE)),
) -> None:
    row = _get(db, control_id)
    record_audit(db, action="INGESTION_CONTROL_DELETED", user=user, entity_type="ingestion_control",
                 entity_id=row.id, detail={"nome_tabela": row.nome_tabela})
    db.delete(row)
    db.commit()


@router.post("/{control_id}/activate", response_model=IngestionControlOut)
def activate(
    control_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_WRITE)),
) -> IngestionControlOut:
    row = _get(db, control_id)
    row.ativo = True
    row.atualizado_em = _naive_now()
    record_audit(db, action="INGESTION_CONTROL_ACTIVATED", user=user, entity_type="ingestion_control", entity_id=row.id)
    db.commit()
    db.refresh(row)
    return _to_out(db, row)


@router.post("/{control_id}/deactivate", response_model=IngestionControlOut)
def deactivate(
    control_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_WRITE)),
) -> IngestionControlOut:
    row = _get(db, control_id)
    row.ativo = False
    row.atualizado_em = _naive_now()
    record_audit(db, action="INGESTION_CONTROL_DEACTIVATED", user=user, entity_type="ingestion_control", entity_id=row.id)
    db.commit()
    db.refresh(row)
    return _to_out(db, row)


# ─────────────────────────── Destinos da carga (multi-destino) ───────────────────────────

class ControlDestinationIn(BaseModel):
    destination_id: int
    destination_role: str = "primary"        # primary | datalake_copy | audit_copy
    write_order: int = 1
    required: bool = True
    stop_on_failure: bool = True
    # Overrides por-carga (§10): como ESTA carga usa o destino genérico. Nulos → base do destino.
    target_schema: str | None = None
    target_table: str | None = None
    target_relative_path: str | None = None
    write_mode: str | None = None
    file_format: str | None = None
    compression: str | None = None
    partition_columns: list[str] | None = None
    primary_key_columns: list[str] | None = None
    staging_table: str | None = None
    options: dict | None = None


class ControlDestinationPatch(BaseModel):
    destination_role: str | None = None
    write_order: int | None = None
    required: bool | None = None
    stop_on_failure: bool | None = None
    active: bool | None = None
    target_schema: str | None = None
    target_table: str | None = None
    target_relative_path: str | None = None
    write_mode: str | None = None
    file_format: str | None = None
    compression: str | None = None
    partition_columns: list[str] | None = None
    primary_key_columns: list[str] | None = None
    staging_table: str | None = None
    options: dict | None = None


@router.get("/{control_id}/destinations")
def list_control_destinations(
    control_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_READ)),
) -> list[dict]:
    _get(db, control_id)  # 404 se a carga não existir
    return icd.list_links(db, control_id)


@router.post("/{control_id}/destinations", status_code=status.HTTP_201_CREATED)
def add_control_destination(
    control_id: int,
    payload: ControlDestinationIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_WRITE)),
) -> dict:
    _get(db, control_id)
    try:
        link = icd.add_link(db, control_id, destination_id=payload.destination_id,
                            destination_role=payload.destination_role, write_order=payload.write_order,
                            required=payload.required, stop_on_failure=payload.stop_on_failure,
                            **payload.model_dump(exclude={"destination_id", "destination_role",
                                                          "write_order", "required", "stop_on_failure"}))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    record_audit(db, action="INGESTION_CONTROL_DESTINATION_LINKED", user=user,
                 entity_type="ingestion_control", entity_id=control_id,
                 detail={"destination_id": payload.destination_id, "role": payload.destination_role})
    link_id = link.id
    db.commit()
    return icd.link_to_dict(db.get(type(link), link_id), None) | {"control_id": control_id}


@router.patch("/{control_id}/destinations/{link_id}")
def update_control_destination(
    control_id: int, link_id: int, payload: ControlDestinationPatch,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_WRITE)),
) -> dict:
    try:
        link = icd.update_link(db, control_id, link_id, **payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vínculo não encontrado")
    db.commit()
    return {"ok": True, "id": link_id}


@router.delete("/{control_id}/destinations/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_control_destination(
    control_id: int, link_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_CONTROL_WRITE)),
) -> None:
    if not icd.remove_link(db, control_id, link_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vínculo não encontrado")
    record_audit(db, action="INGESTION_CONTROL_DESTINATION_UNLINKED", user=user,
                 entity_type="ingestion_control", entity_id=control_id, detail={"link_id": link_id})
    db.commit()
