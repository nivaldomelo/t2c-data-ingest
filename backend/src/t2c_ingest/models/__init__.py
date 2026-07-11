"""SQLAlchemy models for the T2C Data Ingest schema.

Import order matters for Alembic autogenerate: importing this package registers every model
on ``Base.metadata``.
"""

from t2c_ingest.models.base import Base  # noqa: F401
from t2c_ingest.models.cluster import Cluster  # noqa: F401
from t2c_ingest.models.connection import Connection  # noqa: F401
from t2c_ingest.models.job import JobDefinition  # noqa: F401
from t2c_ingest.models.pipeline import (  # noqa: F401
    PipelineDefinition,
    PipelineExecution,
    PipelineStep,
    PipelineStepDependency,
    PipelineStepExecution,
)
from t2c_ingest.models.execution import (  # noqa: F401
    Execution,
    ExecutionLog,
    ExecutionArtifact,
    RuntimeParameter,
)
from t2c_ingest.models.airflow import AirflowDagImport, AirflowTaskImport  # noqa: F401
from t2c_ingest.models.audit import AuditEvent  # noqa: F401
from t2c_ingest.models.job_code_version import JobCodeVersion  # noqa: F401
from t2c_ingest.models.schedule import JobSchedule, ScheduleRun  # noqa: F401
from t2c_ingest.models.variable import JobVariable, Variable  # noqa: F401
from t2c_ingest.models.tag import JobTag, Tag  # noqa: F401
# Previously missing from autogenerate's view — register every owned table so
# `alembic revision --autogenerate` detects drift instead of silently ignoring them.
from t2c_ingest.models.alert import AlertChannel, AlertNotification  # noqa: F401
from t2c_ingest.models.runtime import RuntimeBuild, RuntimeLibrary, RuntimeValidation  # noqa: F401
from t2c_ingest.models.cluster_library import ClusterLibrary, ClusterLibraryAction, JobLibrary  # noqa: F401
from t2c_ingest.models.backfill import BackfillRun  # noqa: F401
from t2c_ingest.models.data_quality import DqResult  # noqa: F401
from t2c_ingest.models.access import IngestUserAccess  # noqa: F401
from t2c_ingest.models.outbox import IntegrationOutbox  # noqa: F401
from t2c_ingest.models.data_lake import (  # noqa: F401
    DataLakeCatalog,
    DataLakeColumn,
    DataLakeFile,
    DataLakePartition,
    DataLakeQueryHistory,
    DataLakeScanRun,
    DataLakeSchema,
    DataLakeTable,
)
