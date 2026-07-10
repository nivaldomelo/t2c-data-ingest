from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from t2c_ingest.models.base import Base
from t2c_ingest.models.common import TimestampMixin

# nao_analisada | em_analise | migracao_planejada | migrada_parcialmente | migrada | descontinuada
MIGRATION_STATUSES = (
    "nao_analisada",
    "em_analise",
    "migracao_planejada",
    "migrada_parcialmente",
    "migrada",
    "descontinuada",
)


class AirflowDagImport(TimestampMixin, Base):
    """Inventory of a legacy Airflow DAG for controlled, gradual migration.

    This is an inventory only — no DAG is moved or executed from here.
    """

    __tablename__ = "airflow_dag_imports"
    __table_args__ = (UniqueConstraint("dag_name", name="uq_ingest_airflow_dag_imports_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dag_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    schedule: Mapped[str | None] = mapped_column(String(120))
    tags: Mapped[list | None] = mapped_column(JSONB)
    file_path: Mapped[str | None] = mapped_column(String(500))
    migration_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="nao_analisada"
    )
    mapped_pipeline_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_definitions.id", ondelete="SET NULL"), index=True
    )
    technical_notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(255))

    tasks: Mapped[list["AirflowTaskImport"]] = relationship(
        "AirflowTaskImport", back_populates="dag", cascade="all, delete-orphan"
    )


class AirflowTaskImport(TimestampMixin, Base):
    __tablename__ = "airflow_task_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    dag_import_id: Mapped[int] = mapped_column(
        ForeignKey("airflow_dag_imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(String(200), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(150))
    upstream_tasks: Mapped[list | None] = mapped_column(JSONB)
    mapped_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_steps.id", ondelete="SET NULL"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    dag: Mapped["AirflowDagImport"] = relationship("AirflowDagImport", back_populates="tasks")
