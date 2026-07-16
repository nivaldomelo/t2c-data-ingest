"""Vínculo Controle de Ingestão → N destinos (carga multi-destino).

Cada linha liga um registro do Controle de Ingestão (controle.t2c_data_controle_ingestao) a um
Destino declarativo (t2c_data_ingest.destinations) com um papel (primary/datalake_copy/audit_copy),
ordem de escrita e obrigatoriedade. Vive no schema do ingest (t2c_data_ingest); sem FK ao controle
(que fica em outro schema/metadata) — a integridade é validada na aplicação.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
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

    # Overrides por-carga: como ESTA carga usa o destino genérico. Quando nulo, o runner cai de
    # volta ao valor-base do próprio destino (retrocompat). §10 do pedido.
    target_schema: Mapped[str | None] = mapped_column(String(150))
    target_table: Mapped[str | None] = mapped_column(String(255))
    target_relative_path: Mapped[str | None] = mapped_column(Text)
    write_mode: Mapped[str | None] = mapped_column(String(50))
    file_format: Mapped[str | None] = mapped_column(String(50))
    compression: Mapped[str | None] = mapped_column(String(50))
    partition_columns: Mapped[list | None] = mapped_column(JSONB)
    primary_key_columns: Mapped[list | None] = mapped_column(JSONB)
    staging_table: Mapped[str | None] = mapped_column(String(255))
    options: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
