"""SQLAlchemy models for the T2C Data Ingest schema.

Import order matters for Alembic autogenerate: importing this package registers every model
on ``Base.metadata``.
"""

from t2c_ingest.models.base import Base  # noqa: F401
from t2c_ingest.models.cluster import Cluster  # noqa: F401
from t2c_ingest.models.connection import Connection  # noqa: F401
from t2c_ingest.models.job import JobDefinition  # noqa: F401
from t2c_ingest.models.pipeline import PipelineDefinition, PipelineStep  # noqa: F401
from t2c_ingest.models.execution import (  # noqa: F401
    Execution,
    ExecutionLog,
    ExecutionArtifact,
    RuntimeParameter,
)
from t2c_ingest.models.airflow import AirflowDagImport, AirflowTaskImport  # noqa: F401
from t2c_ingest.models.audit import AuditEvent  # noqa: F401
