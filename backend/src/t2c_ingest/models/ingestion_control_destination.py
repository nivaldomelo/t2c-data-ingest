"""Vínculo Controle de Ingestão → N destinos (carga multi-destino).

Cada linha liga um registro do Controle de Ingestão (controle.t2c_data_controle_ingestao) a um
Destino declarativo (t2c_data_ingest.destinations) com um papel (primary/datalake_copy/audit_copy),
ordem de escrita e obrigatoriedade. Vive no schema do ingest (t2c_data_ingest); sem FK ao controle
(que fica em outro schema/metadata) — a integridade é validada na aplicação.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from t2c_ingest.models.base import Base

# Papéis suportados de um destino dentro de uma carga.
DESTINATION_ROLES = ("primary", "datalake_copy", "audit_copy")


class IngestionControlDestination(Base):
    __tablename__ = "ingestion_control_destinations"
    __table_args__ = (
        Index("idx_ic_destinations_control", "control_id"),
        Index("idx_ic_destinations_destination", "destination_id"),
        Index("uq_ic_destination_role", "control_id", "destination_id", "destination_role", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_id: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_role: Mapped[str] = mapped_column(String(50), nullable=False)
    write_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    stop_on_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
