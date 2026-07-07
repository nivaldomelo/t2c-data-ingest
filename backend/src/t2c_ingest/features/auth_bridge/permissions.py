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
INGEST_AIRFLOW_READ = "ingest:airflow:read"
INGEST_AIRFLOW_MIGRATE = "ingest:airflow:migrate"
INGEST_CONNECTIONS_READ = "ingest:connections:read"
INGEST_CONNECTIONS_WRITE = "ingest:connections:write"
INGEST_CONNECTIONS_TEST = "ingest:connections:test"
INGEST_CONNECTIONS_DELETE = "ingest:connections:delete"
# Reading a job's source code (potentially sensitive). Admin/editor only by default.
INGEST_JOBS_CODE_READ = "ingest:jobs:code:read"

ALL_PERMISSIONS = {
    INGEST_READ,
    INGEST_RUN,
    INGEST_WRITE,
    INGEST_ADMIN,
    INGEST_LOGS_READ,
    INGEST_CLUSTERS_READ,
    INGEST_CLUSTERS_MANAGE,
    INGEST_AIRFLOW_READ,
    INGEST_AIRFLOW_MIGRATE,
    INGEST_CONNECTIONS_READ,
    INGEST_CONNECTIONS_WRITE,
    INGEST_CONNECTIONS_TEST,
    INGEST_CONNECTIONS_DELETE,
    INGEST_JOBS_CODE_READ,
}

# Mapping from t2c_data role -> ingest permissions.
# IMPORTANT: viewer, stewardship and data_owner must NOT receive administrative permissions,
# matching the rule already enforced in t2c_data.
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        INGEST_ADMIN,
        INGEST_READ,
        INGEST_WRITE,
        INGEST_RUN,
        INGEST_LOGS_READ,
        INGEST_CLUSTERS_READ,
        INGEST_CLUSTERS_MANAGE,
        INGEST_AIRFLOW_READ,
        INGEST_AIRFLOW_MIGRATE,
        INGEST_CONNECTIONS_READ,
        INGEST_CONNECTIONS_WRITE,
        INGEST_CONNECTIONS_TEST,
        INGEST_CONNECTIONS_DELETE,
        INGEST_JOBS_CODE_READ,
    },
    "editor": {
        INGEST_READ,
        INGEST_WRITE,
        INGEST_RUN,
        INGEST_LOGS_READ,
        INGEST_CLUSTERS_READ,
        INGEST_AIRFLOW_READ,
        INGEST_CONNECTIONS_READ,
        INGEST_CONNECTIONS_WRITE,
        INGEST_CONNECTIONS_TEST,
        INGEST_JOBS_CODE_READ,
    },
    "viewer": {
        INGEST_READ,
        INGEST_LOGS_READ,
        INGEST_CONNECTIONS_READ,
    },
    "stewardship": {
        INGEST_READ,
        INGEST_LOGS_READ,
        INGEST_CONNECTIONS_READ,
    },
    "data_owner": {
        INGEST_READ,
        INGEST_RUN,
        INGEST_LOGS_READ,
        INGEST_CONNECTIONS_READ,
        INGEST_CONNECTIONS_TEST,
    },
}

# Roles that are administrators of the base platform always get full ingest access.
ADMIN_ROLE_NAMES = {"admin", "superadmin", "owner"}


def permissions_for_roles(role_names: set[str]) -> set[str]:
    """Resolve the effective ingest permissions for a set of t2c_data role names."""
    if role_names & ADMIN_ROLE_NAMES:
        return set(ALL_PERMISSIONS)
    granted: set[str] = set()
    for role in role_names:
        granted |= ROLE_PERMISSIONS.get(role, set())
    return granted
