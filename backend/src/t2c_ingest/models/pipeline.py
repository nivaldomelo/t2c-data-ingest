from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from t2c_ingest.models.base import Base
from t2c_ingest.models.common import TimestampMixin

# bronze | silver | gold | full
PIPELINE_LAYERS = ("bronze", "silver", "gold", "full")


class PipelineDefinition(TimestampMixin, Base):
    """A simplified DAG: an ordered set of steps, each bound to a job."""

    __tablename__ = "pipeline_definitions"
    __table_args__ = (UniqueConstraint("name", name="uq_ingest_pipeline_definitions_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(120))
    layer: Mapped[str | None] = mapped_column(String(20))
    tags: Mapped[list | None] = mapped_column(JSONB)
    technical_owner: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(255))

    steps: Mapped[list["PipelineStep"]] = relationship(
        "PipelineStep",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="PipelineStep.order_index",
    )


class PipelineStep(TimestampMixin, Base):
    __tablename__ = "pipeline_steps"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "order_index", name="uq_ingest_pipeline_steps_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(150))
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_definitions.id", ondelete="SET NULL"), index=True
    )
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    # ids of prior steps this one depends on (within the same pipeline)
    depends_on: Mapped[list | None] = mapped_column(JSONB)
    stop_on_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)

    pipeline: Mapped["PipelineDefinition"] = relationship(
        "PipelineDefinition", back_populates="steps"
    )
