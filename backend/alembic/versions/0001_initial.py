"""initial ingest schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from t2c_ingest.core.config import settings

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = settings.db_schema or "t2c_data_ingest"


def _ts(*extra):
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *extra,
    )


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')

    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("type", sa.String(30), nullable=False, server_default="local_docker"),
        sa.Column("spark_master_url", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("worker_count", sa.Integer()),
        sa.Column("total_cores", sa.Integer()),
        sa.Column("total_memory", sa.String(30)),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(255)),
        *_ts(),
        sa.UniqueConstraint("name", name="uq_ingest_clusters_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "job_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("script_path", sa.String(500)),
        sa.Column("main_class", sa.String(255)),
        sa.Column("sql_statement", sa.Text()),
        sa.Column("arguments", postgresql.JSONB()),
        sa.Column("env_vars", postgresql.JSONB()),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.clusters.id", ondelete="SET NULL")),
        sa.Column("engine", sa.String(20)),
        sa.Column("timeout_seconds", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        *_ts(),
        sa.UniqueConstraint("name", name="uq_ingest_job_definitions_name"),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_job_definitions_cluster_id", "job_definitions", ["cluster_id"], schema=SCHEMA)

    op.create_table(
        "pipeline_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("domain", sa.String(120)),
        sa.Column("layer", sa.String(20)),
        sa.Column("tags", postgresql.JSONB()),
        sa.Column("technical_owner", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(255)),
        *_ts(),
        sa.UniqueConstraint("name", name="uq_ingest_pipeline_definitions_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "pipeline_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.pipeline_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150)),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.job_definitions.id", ondelete="SET NULL")),
        sa.Column("parameters", postgresql.JSONB()),
        sa.Column("depends_on", postgresql.JSONB()),
        sa.Column("stop_on_error", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeout_seconds", sa.Integer()),
        *_ts(),
        sa.UniqueConstraint("pipeline_id", "order_index", name="uq_ingest_pipeline_steps_order"),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_pipeline_steps_pipeline_id", "pipeline_steps", ["pipeline_id"], schema=SCHEMA)
    op.create_index("ix_ingest_pipeline_steps_job_id", "pipeline_steps", ["job_id"], schema=SCHEMA)

    op.create_table(
        "executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.job_definitions.id", ondelete="SET NULL")),
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.pipeline_definitions.id", ondelete="SET NULL")),
        sa.Column("target_name", sa.String(200)),
        sa.Column("job_type", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("engine", sa.String(20)),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.clusters.id", ondelete="SET NULL")),
        sa.Column("parameters", postgresql.JSONB()),
        sa.Column("triggered_by", sa.String(255)),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("final_message", sa.Text()),
        sa.Column("error_trace", sa.Text()),
        sa.Column("parent_execution_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.executions.id", ondelete="CASCADE")),
        sa.Column("step_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.pipeline_steps.id", ondelete="SET NULL")),
        *_ts(),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_executions_status", "executions", ["status"], schema=SCHEMA)
    op.create_index("ix_ingest_executions_status_started", "executions", ["status", "started_at"], schema=SCHEMA)
    op.create_index("ix_ingest_executions_triggered_by", "executions", ["triggered_by"], schema=SCHEMA)
    op.create_index("ix_ingest_executions_job_id", "executions", ["job_id"], schema=SCHEMA)
    op.create_index("ix_ingest_executions_pipeline_id", "executions", ["pipeline_id"], schema=SCHEMA)
    op.create_index("ix_ingest_executions_parent", "executions", ["parent_execution_id"], schema=SCHEMA)

    op.create_table(
        "execution_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("execution_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.Integer()),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.String(10), nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True)),
        *_ts(),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_execution_logs_execution_seq", "execution_logs", ["execution_id", "seq"], schema=SCHEMA)

    op.create_table(
        "execution_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("execution_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(30)),
        sa.Column("uri", sa.Text()),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("meta", postgresql.JSONB()),
        *_ts(),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_execution_artifacts_execution_id", "execution_artifacts", ["execution_id"], schema=SCHEMA)

    op.create_table(
        "runtime_parameters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("execution_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text()),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_ts(),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_runtime_parameters_execution_id", "runtime_parameters", ["execution_id"], schema=SCHEMA)

    op.create_table(
        "airflow_dag_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dag_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("schedule", sa.String(120)),
        sa.Column("tags", postgresql.JSONB()),
        sa.Column("file_path", sa.String(500)),
        sa.Column("migration_status", sa.String(30), nullable=False, server_default="nao_analisada"),
        sa.Column("mapped_pipeline_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.pipeline_definitions.id", ondelete="SET NULL")),
        sa.Column("technical_notes", sa.Text()),
        sa.Column("created_by", sa.String(255)),
        *_ts(),
        sa.UniqueConstraint("dag_name", name="uq_ingest_airflow_dag_imports_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "airflow_task_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dag_import_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.airflow_dag_imports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("operator", sa.String(150)),
        sa.Column("upstream_tasks", postgresql.JSONB()),
        sa.Column("mapped_step_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.pipeline_steps.id", ondelete="SET NULL")),
        sa.Column("notes", sa.Text()),
        *_ts(),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_airflow_task_imports_dag", "airflow_task_imports", ["dag_import_id"], schema=SCHEMA)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(60)),
        sa.Column("entity_id", sa.String(80)),
        sa.Column("user_email", sa.String(255)),
        sa.Column("user_id", sa.Integer()),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("detail", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_ingest_audit_events_action", "audit_events", ["action"], schema=SCHEMA)
    op.create_index("ix_ingest_audit_events_created_at", "audit_events", ["created_at"], schema=SCHEMA)


def downgrade() -> None:
    for table in (
        "audit_events",
        "airflow_task_imports",
        "airflow_dag_imports",
        "runtime_parameters",
        "execution_artifacts",
        "execution_logs",
        "executions",
        "pipeline_steps",
        "pipeline_definitions",
        "job_definitions",
        "clusters",
    ):
        op.drop_table(table, schema=SCHEMA)
