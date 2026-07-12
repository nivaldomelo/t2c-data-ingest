from __future__ import annotations

# Ingest-specific permissions. These are NOT stored in t2c_data; they are derived from the
# existing role names so no changes to the base product's users/roles are required.
INGEST_READ = "ingest:read"
INGEST_RUN = "ingest:run"
INGEST_WRITE = "ingest:write"
INGEST_ADMIN = "ingest:admin"
INGEST_LOGS_READ = "ingest:logs:read"
INGEST_CLUSTERS_READ = "ingest:clusters:read"
INGEST_CLUSTERS_MANAGE = "ingest:clusters:manage"
INGEST_CLUSTERS_TEST = "ingest:clusters:test"
INGEST_CLUSTERS_VALIDATE = "ingest:clusters:validate"
INGEST_AIRFLOW_READ = "ingest:airflow:read"
INGEST_AIRFLOW_MIGRATE = "ingest:airflow:migrate"
INGEST_CONNECTIONS_READ = "ingest:connections:read"
INGEST_CONNECTIONS_WRITE = "ingest:connections:write"
INGEST_CONNECTIONS_TEST = "ingest:connections:test"
INGEST_CONNECTIONS_DELETE = "ingest:connections:delete"
# S3 / Data Lake object access via a connection.
INGEST_S3_READ = "ingest:s3:read"
INGEST_S3_WRITE = "ingest:s3:write"
INGEST_S3_LIST = "ingest:s3:list"
# Data Lake explorer / catalog (Bronze/Silver/Gold as schemas, folders as tables).
INGEST_DATA_LAKE_READ = "ingest:data-lake:read"
INGEST_DATA_LAKE_SCAN = "ingest:data-lake:scan"
INGEST_DATA_LAKE_QUERY = "ingest:data-lake:query"
INGEST_DATA_LAKE_ADMIN = "ingest:data-lake:admin"
# Creating a job (admin/editor).
INGEST_JOBS_CREATE = "ingest:jobs:create"
# Deleting a job (soft delete + code archival). Reserved to admins in this version.
INGEST_JOBS_DELETE = "ingest:jobs:delete"
# Reading / editing a job's source code (potentially sensitive).
INGEST_JOBS_CODE_READ = "ingest:jobs:code:read"
INGEST_JOBS_CODE_WRITE = "ingest:jobs:code:write"
INGEST_JOBS_CODE_CREATE = "ingest:jobs:code:create"
INGEST_JOBS_CODE_DELETE = "ingest:jobs:code:delete"
INGEST_JOBS_CODE_RENAME = "ingest:jobs:code:rename"
# Job schedules (automatic execution).
INGEST_SCHEDULES_READ = "ingest:schedules:read"
INGEST_SCHEDULES_WRITE = "ingest:schedules:write"
INGEST_SCHEDULES_DELETE = "ingest:schedules:delete"
INGEST_SCHEDULES_ENABLE = "ingest:schedules:enable"
INGEST_SCHEDULES_DISABLE = "ingest:schedules:disable"
INGEST_SCHEDULES_RUN = "ingest:schedules:run"
# Ingestion control table (controle.t2c_data_controle_ingestao).
INGEST_CONTROL_READ = "ingest:control:read"
INGEST_CONTROL_WRITE = "ingest:control:write"
INGEST_CONTROL_DELETE = "ingest:control:delete"
# Reusable variables (parameters for jobs/pipelines).
INGEST_VARIABLES_READ = "ingest:variables:read"
INGEST_VARIABLES_WRITE = "ingest:variables:write"
INGEST_VARIABLES_DELETE = "ingest:variables:delete"
INGEST_VARIABLES_SECRET_READ = "ingest:variables:secret:read"
INGEST_VARIABLES_SECRET_WRITE = "ingest:variables:secret:write"
# Pipelines (visual builder + execution).
INGEST_PIPELINES_READ = "ingest:pipelines:read"
INGEST_PIPELINES_WRITE = "ingest:pipelines:write"
INGEST_PIPELINES_DELETE = "ingest:pipelines:delete"
INGEST_PIPELINES_RUN = "ingest:pipelines:run"
INGEST_PIPELINES_BUILDER = "ingest:pipelines:builder"
# Cluster libraries (managed pip packages).
INGEST_LIBRARIES_READ = "ingest:libraries:read"
INGEST_LIBRARIES_INSTALL = "ingest:libraries:install"
INGEST_LIBRARIES_UNINSTALL = "ingest:libraries:uninstall"
INGEST_LIBRARIES_MANAGE = "ingest:libraries:manage"
# Data quality / lineage.
INGEST_QUALITY_READ = "ingest:quality:read"
# Alerts / notifications (channels + delivery).
INGEST_ALERTS_READ = "ingest:alerts:read"
INGEST_ALERTS_MANAGE = "ingest:alerts:manage"
# Backfill / reprocessing (reprocess jobs/pipelines/control groups; watermark reset is separate).
INGEST_BACKFILL_RUN = "ingest:backfill:run"
INGEST_BACKFILL_WATERMARK = "ingest:backfill:watermark"
# Runtime environment (managed image: libraries manifest + builds + cluster validation).
INGEST_RUNTIME_READ = "ingest:runtime:read"
INGEST_RUNTIME_LIBRARIES_WRITE = "ingest:runtime:libraries:write"
INGEST_RUNTIME_BUILD = "ingest:runtime:build"
INGEST_RUNTIME_ACTIVATE = "ingest:runtime:activate"
INGEST_RUNTIME_VALIDATE = "ingest:runtime:validate"
# Tags (job organization/search).
INGEST_TAGS_READ = "ingest:tags:read"
INGEST_TAGS_WRITE = "ingest:tags:write"
INGEST_TAGS_DELETE = "ingest:tags:delete"
INGEST_JOBS_TAGS_WRITE = "ingest:jobs:tags:write"

ALL_PERMISSIONS = {
    INGEST_READ,
    INGEST_RUN,
    INGEST_WRITE,
    INGEST_ADMIN,
    INGEST_LOGS_READ,
    INGEST_CLUSTERS_READ,
    INGEST_CLUSTERS_MANAGE,
    INGEST_CLUSTERS_TEST,
    INGEST_CLUSTERS_VALIDATE,
    INGEST_AIRFLOW_READ,
    INGEST_AIRFLOW_MIGRATE,
    INGEST_CONNECTIONS_READ,
    INGEST_CONNECTIONS_WRITE,
    INGEST_CONNECTIONS_TEST,
    INGEST_CONNECTIONS_DELETE,
    INGEST_S3_READ,
    INGEST_S3_WRITE,
    INGEST_S3_LIST,
    INGEST_DATA_LAKE_READ,
    INGEST_DATA_LAKE_SCAN,
    INGEST_DATA_LAKE_QUERY,
    INGEST_DATA_LAKE_ADMIN,
    INGEST_JOBS_CREATE,
    INGEST_JOBS_DELETE,
    INGEST_JOBS_CODE_READ,
    INGEST_JOBS_CODE_WRITE,
    INGEST_JOBS_CODE_CREATE,
    INGEST_JOBS_CODE_DELETE,
    INGEST_JOBS_CODE_RENAME,
    INGEST_SCHEDULES_READ,
    INGEST_SCHEDULES_WRITE,
    INGEST_SCHEDULES_DELETE,
    INGEST_SCHEDULES_ENABLE,
    INGEST_SCHEDULES_DISABLE,
    INGEST_SCHEDULES_RUN,
    INGEST_CONTROL_READ,
    INGEST_CONTROL_WRITE,
    INGEST_CONTROL_DELETE,
    INGEST_VARIABLES_READ,
    INGEST_VARIABLES_WRITE,
    INGEST_VARIABLES_DELETE,
    INGEST_VARIABLES_SECRET_READ,
    INGEST_VARIABLES_SECRET_WRITE,
    INGEST_PIPELINES_READ,
    INGEST_PIPELINES_WRITE,
    INGEST_PIPELINES_DELETE,
    INGEST_PIPELINES_RUN,
    INGEST_PIPELINES_BUILDER,
    INGEST_LIBRARIES_READ,
    INGEST_LIBRARIES_INSTALL,
    INGEST_LIBRARIES_UNINSTALL,
    INGEST_LIBRARIES_MANAGE,
    INGEST_RUNTIME_READ,
    INGEST_RUNTIME_LIBRARIES_WRITE,
    INGEST_RUNTIME_BUILD,
    INGEST_RUNTIME_ACTIVATE,
    INGEST_RUNTIME_VALIDATE,
    INGEST_BACKFILL_RUN,
    INGEST_BACKFILL_WATERMARK,
    INGEST_QUALITY_READ,
    INGEST_ALERTS_READ,
    INGEST_ALERTS_MANAGE,
    INGEST_TAGS_READ,
    INGEST_TAGS_WRITE,
    INGEST_TAGS_DELETE,
    INGEST_JOBS_TAGS_WRITE,
}

# Mapping from t2c_data role -> ingest permissions.
# IMPORTANT: viewer, stewardship and data_owner must NOT receive administrative permissions,
# matching the rule already enforced in t2c_data.
# DEPRECATED / UNUSED. The live access model is resolve_ingest_permissions() (admin-only
# writes, granted users read-only). This legacy per-role map is NOT consulted anywhere — do
# NOT wire it back into deps.py, or editor/data_owner would silently regain write access.
_DEPRECATED_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        INGEST_ADMIN,
        INGEST_READ,
        INGEST_WRITE,
        INGEST_RUN,
        INGEST_LOGS_READ,
        INGEST_CLUSTERS_READ,
        INGEST_CLUSTERS_MANAGE,
        INGEST_CLUSTERS_TEST,
        INGEST_CLUSTERS_VALIDATE,
        INGEST_AIRFLOW_READ,
        INGEST_AIRFLOW_MIGRATE,
        INGEST_CONNECTIONS_READ,
        INGEST_CONNECTIONS_WRITE,
        INGEST_CONNECTIONS_TEST,
        INGEST_CONNECTIONS_DELETE,
        INGEST_JOBS_CREATE,
        INGEST_JOBS_DELETE,
        INGEST_JOBS_CODE_READ,
        INGEST_JOBS_CODE_WRITE,
        INGEST_JOBS_CODE_CREATE,
        INGEST_JOBS_CODE_DELETE,
        INGEST_JOBS_CODE_RENAME,
        INGEST_SCHEDULES_READ,
        INGEST_SCHEDULES_WRITE,
        INGEST_SCHEDULES_DELETE,
        INGEST_SCHEDULES_ENABLE,
        INGEST_SCHEDULES_DISABLE,
        INGEST_SCHEDULES_RUN,
        INGEST_CONTROL_READ,
        INGEST_CONTROL_WRITE,
        INGEST_CONTROL_DELETE,
        INGEST_VARIABLES_READ,
        INGEST_VARIABLES_WRITE,
        INGEST_VARIABLES_DELETE,
        INGEST_VARIABLES_SECRET_READ,
        INGEST_VARIABLES_SECRET_WRITE,
        INGEST_PIPELINES_READ,
        INGEST_PIPELINES_WRITE,
        INGEST_PIPELINES_DELETE,
        INGEST_PIPELINES_RUN,
        INGEST_PIPELINES_BUILDER,
        INGEST_LIBRARIES_READ,
        INGEST_LIBRARIES_INSTALL,
        INGEST_LIBRARIES_UNINSTALL,
        INGEST_LIBRARIES_MANAGE,
        INGEST_RUNTIME_READ,
        INGEST_RUNTIME_LIBRARIES_WRITE,
        INGEST_RUNTIME_BUILD,
        INGEST_RUNTIME_ACTIVATE,
        INGEST_RUNTIME_VALIDATE,
        INGEST_BACKFILL_RUN,
        INGEST_BACKFILL_WATERMARK,
        INGEST_QUALITY_READ,
        INGEST_ALERTS_READ,
        INGEST_ALERTS_MANAGE,
        INGEST_TAGS_READ,
        INGEST_TAGS_WRITE,
        INGEST_TAGS_DELETE,
        INGEST_JOBS_TAGS_WRITE,
    },
    "editor": {
        INGEST_READ,
        INGEST_WRITE,
        INGEST_RUN,
        INGEST_LOGS_READ,
        INGEST_CLUSTERS_READ,
        INGEST_CLUSTERS_TEST,
        INGEST_CLUSTERS_VALIDATE,
        INGEST_AIRFLOW_READ,
        INGEST_CONNECTIONS_READ,
        INGEST_CONNECTIONS_WRITE,
        INGEST_CONNECTIONS_TEST,
        INGEST_JOBS_CREATE,
        INGEST_JOBS_CODE_READ,
        INGEST_JOBS_CODE_WRITE,
        INGEST_JOBS_CODE_CREATE,
        INGEST_JOBS_CODE_DELETE,
        INGEST_JOBS_CODE_RENAME,
        INGEST_SCHEDULES_READ,
        INGEST_SCHEDULES_WRITE,
        INGEST_SCHEDULES_ENABLE,
        INGEST_SCHEDULES_DISABLE,
        INGEST_SCHEDULES_RUN,
        INGEST_CONTROL_READ,
        INGEST_CONTROL_WRITE,
        INGEST_VARIABLES_READ,
        INGEST_VARIABLES_WRITE,
        INGEST_VARIABLES_SECRET_WRITE,
        INGEST_PIPELINES_READ,
        INGEST_PIPELINES_WRITE,
        INGEST_PIPELINES_RUN,
        INGEST_PIPELINES_BUILDER,
        INGEST_LIBRARIES_READ,
        INGEST_LIBRARIES_INSTALL,
        INGEST_LIBRARIES_UNINSTALL,
        INGEST_RUNTIME_READ,
        INGEST_RUNTIME_LIBRARIES_WRITE,
        INGEST_RUNTIME_BUILD,
        INGEST_RUNTIME_VALIDATE,
        INGEST_BACKFILL_RUN,
        INGEST_BACKFILL_WATERMARK,
        INGEST_QUALITY_READ,
        INGEST_ALERTS_READ,
        INGEST_ALERTS_MANAGE,
        INGEST_TAGS_READ,
        INGEST_TAGS_WRITE,
        INGEST_JOBS_TAGS_WRITE,
    },
    "viewer": {
        INGEST_READ,
        INGEST_LOGS_READ,
        INGEST_CLUSTERS_READ,
        INGEST_CONNECTIONS_READ,
        INGEST_SCHEDULES_READ,
        INGEST_CONTROL_READ,
        INGEST_VARIABLES_READ,
        INGEST_PIPELINES_READ,
        INGEST_LIBRARIES_READ,
        INGEST_RUNTIME_READ,
        INGEST_QUALITY_READ,
        INGEST_ALERTS_READ,
        INGEST_TAGS_READ,
    },
    "stewardship": {
        INGEST_READ,
        INGEST_LOGS_READ,
        INGEST_CLUSTERS_READ,
        INGEST_CONNECTIONS_READ,
        INGEST_JOBS_CODE_READ,
        INGEST_SCHEDULES_READ,
        INGEST_CONTROL_READ,
        INGEST_VARIABLES_READ,
        INGEST_PIPELINES_READ,
        INGEST_LIBRARIES_READ,
        INGEST_RUNTIME_READ,
        INGEST_QUALITY_READ,
        INGEST_ALERTS_READ,
        INGEST_TAGS_READ,
    },
    "data_owner": {
        INGEST_READ,
        INGEST_RUN,
        INGEST_LOGS_READ,
        INGEST_CLUSTERS_READ,
        INGEST_CLUSTERS_VALIDATE,
        INGEST_CONNECTIONS_READ,
        INGEST_CONNECTIONS_TEST,
        INGEST_JOBS_CODE_READ,
        INGEST_SCHEDULES_READ,
        INGEST_SCHEDULES_RUN,
        INGEST_CONTROL_READ,
        INGEST_VARIABLES_READ,
        INGEST_PIPELINES_READ,
        INGEST_PIPELINES_RUN,
        INGEST_LIBRARIES_READ,
        INGEST_RUNTIME_READ,
        INGEST_RUNTIME_VALIDATE,
        INGEST_BACKFILL_RUN,
        INGEST_QUALITY_READ,
        INGEST_ALERTS_READ,
        INGEST_TAGS_READ,
    },
}

# Roles that are administrators of the base platform always get full ingest access.
ADMIN_ROLE_NAMES = {"admin", "superadmin", "owner"}

# View-only permission set: every read permission and nothing that mutates, runs or reveals
# secrets. Granted to any user an admin has explicitly allowed into the tool. Excludes
# INGEST_ADMIN and INGEST_VARIABLES_SECRET_READ.
READ_ONLY_PERMISSIONS = frozenset({
    INGEST_READ,
    INGEST_LOGS_READ,
    INGEST_CLUSTERS_READ,
    INGEST_AIRFLOW_READ,
    INGEST_CONNECTIONS_READ,
    INGEST_S3_READ,
    INGEST_S3_LIST,
    # Data Lake: view-only users may browse the catalog. Running a scan or a quick query
    # spins up Spark (a mutating/compute action) and stays admin-only.
    INGEST_DATA_LAKE_READ,
    # NOTE: INGEST_JOBS_CODE_READ is deliberately NOT here — job source can embed hardcoded
    # credentials, so raw code is admin-only (consistent with masking variable/connection
    # secrets from view-only users). Re-add if code visibility is desired for viewers.
    INGEST_SCHEDULES_READ,
    INGEST_CONTROL_READ,
    INGEST_VARIABLES_READ,
    INGEST_PIPELINES_READ,
    INGEST_LIBRARIES_READ,
    INGEST_QUALITY_READ,
    INGEST_ALERTS_READ,
    INGEST_RUNTIME_READ,
    INGEST_TAGS_READ,
})


def resolve_ingest_permissions(role_names: set[str], has_access: bool) -> set[str]:
    """Access model for the ingest tool.

    - t2c_data admin roles (admin/superadmin/owner) -> FULL permissions: only admins can
      create, run, edit or delete jobs, pipelines, connections, libraries, etc.
    - any other user an admin has explicitly granted access to -> READ-ONLY (view everything,
      change nothing).
    - everyone else -> no access at all (empty set), even though credentials are shared with
      t2c_data. Access is opt-in and admin-managed.

    The legacy per-role grants (editor/data_owner/…) intentionally no longer apply.
    """
    if role_names & ADMIN_ROLE_NAMES:
        return set(ALL_PERMISSIONS)
    if has_access:
        return set(READ_ONLY_PERMISSIONS)
    return set()
