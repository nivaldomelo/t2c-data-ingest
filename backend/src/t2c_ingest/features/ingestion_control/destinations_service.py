"""Vínculos Controle de Ingestão → destinos (carga multi-destino).

CRUD dos vínculos + resolução ordenada usada pelo worker/job genérico para gravar em N destinos
(ex.: cópia S3 Bronze antes do destino relacional PostgreSQL).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.models.destination import Destination
from t2c_ingest.models.ingestion_control_destination import (
    DESTINATION_ROLES,
    IngestionControlDestination,
)


# Overrides por-carga persistidos no vínculo (quando nulos, o runner usa a base do destino).
_OVERRIDE_FIELDS = (
    "target_schema", "target_table", "target_relative_path", "write_mode", "file_format",
    "compression", "partition_columns", "primary_key_columns", "staging_table", "options",
)


def _overrides(link: IngestionControlDestination) -> dict:
    return {k: getattr(link, k) for k in _OVERRIDE_FIELDS}


def _dest_brief(d: Destination | None) -> dict | None:
    if not d:
        return None
    return {
        "id": d.id, "name": d.name, "destination_type": d.destination_type,
        "connection_id": d.connection_id, "target_layer": d.target_layer,
        "target_schema": d.target_schema, "target_table": d.target_table,
        "target_database": d.target_database, "staging_schema": d.staging_schema,
        "target_bucket": d.target_bucket, "target_prefix": d.target_prefix, "target_path": d.target_path,
        "file_format": d.file_format, "compression": d.compression, "write_mode": d.write_mode,
        "partition_columns": d.partition_columns, "is_template": d.is_template,
    }


def link_to_dict(link: IngestionControlDestination, dest: Destination | None) -> dict:
    return {
        "id": link.id, "control_id": link.control_id, "destination_id": link.destination_id,
        "destination_role": link.destination_role, "write_order": link.write_order,
        "required": link.required, "stop_on_failure": link.stop_on_failure, "active": link.active,
        **_overrides(link),
        "destination": _dest_brief(dest),
    }


def list_links(db: Session, control_id: int) -> list[dict]:
    links = db.scalars(
        select(IngestionControlDestination)
        .where(IngestionControlDestination.control_id == control_id)
        .order_by(IngestionControlDestination.write_order, IngestionControlDestination.id)
    ).all()
    dmap = {}
    if links:
        ids = {l.destination_id for l in links}
        dmap = {d.id: d for d in db.scalars(select(Destination).where(Destination.id.in_(ids))).all()}
    return [link_to_dict(l, dmap.get(l.destination_id)) for l in links]


def add_link(db: Session, control_id: int, *, destination_id: int, destination_role: str,
             write_order: int = 1, required: bool = True, stop_on_failure: bool = True,
             **overrides) -> IngestionControlDestination:
    if destination_role not in DESTINATION_ROLES:
        raise ValueError(f"Papel inválido: {destination_role}. Use um de {DESTINATION_ROLES}.")
    if not db.get(Destination, destination_id):
        raise ValueError(f"Destino #{destination_id} não encontrado.")
    dup = db.scalar(select(IngestionControlDestination.id).where(
        IngestionControlDestination.control_id == control_id,
        IngestionControlDestination.destination_id == destination_id,
        IngestionControlDestination.destination_role == destination_role,
    ))
    if dup:
        raise ValueError("Este destino já está vinculado a esta carga com o mesmo papel.")
    link = IngestionControlDestination(
        control_id=control_id, destination_id=destination_id, destination_role=destination_role,
        write_order=write_order, required=required, stop_on_failure=stop_on_failure, active=True,
        **{k: overrides[k] for k in _OVERRIDE_FIELDS if overrides.get(k) is not None},
    )
    db.add(link)
    db.flush()
    return link


def remove_link(db: Session, control_id: int, link_id: int) -> bool:
    link = db.get(IngestionControlDestination, link_id)
    if not link or link.control_id != control_id:
        return False
    db.delete(link)
    db.flush()
    return True


def update_link(db: Session, control_id: int, link_id: int, **fields) -> IngestionControlDestination | None:
    link = db.get(IngestionControlDestination, link_id)
    if not link or link.control_id != control_id:
        return None
    for k in ("destination_role", "write_order", "required", "stop_on_failure", "active"):
        if k in fields and fields[k] is not None:
            if k == "destination_role" and fields[k] not in DESTINATION_ROLES:
                raise ValueError(f"Papel inválido: {fields[k]}.")
            setattr(link, k, fields[k])
    # Overrides: aceitam limpar (setar None explicitamente) via presença da chave.
    for k in _OVERRIDE_FIELDS:
        if k in fields:
            setattr(link, k, fields[k])
    link.updated_at = datetime.now(timezone.utc)
    db.flush()
    return link


def resolve_control_destinations(db: Session, control_id: int) -> list[dict]:
    """Destinos ativos de uma carga, ordenados por write_order, com o Destino resolvido.
    Usado pelo job genérico/worker para gravar em N destinos na ordem correta."""
    links = db.scalars(
        select(IngestionControlDestination)
        .where(IngestionControlDestination.control_id == control_id,
               IngestionControlDestination.active.is_(True))
        .order_by(IngestionControlDestination.write_order, IngestionControlDestination.id)
    ).all()
    out = []
    for l in links:
        dest = db.get(Destination, l.destination_id)
        if dest:
            out.append({"role": l.destination_role, "write_order": l.write_order,
                        "required": l.required, "stop_on_failure": l.stop_on_failure,
                        "overrides": _overrides(l), "destination": dest})
    return out
