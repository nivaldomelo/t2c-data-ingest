from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = str(PROJECT_ROOT / ".env")
DEV_ENVIRONMENTS = {"dev", "development", "local", "test"}


def normalize_environment(env: str | None) -> str:
    return (env or "").strip().lower()


def is_dev_environment(env: str | None) -> bool:
    return normalize_environment(env) in DEV_ENVIRONMENTS


class Settings(BaseSettings):
    """Settings for the T2C Data Ingest backend.

    Mirrors the t2c_data backend conventions: single ``.env`` at the repo root, secure
    defaults (unset ENV is treated as production), and a shared JWT secret so tokens issued
    by t2c_data are accepted here without re-issuing credentials.
    """

    app_name: str = "T2C Data Ingest"
    env: str = "production"

    # Same Postgres instance as t2c_data. The ingest product owns ``db_schema`` and only
    # READS from ``reference_schema`` (users/roles/permissions live in t2c_data).
    database_url: str
    db_schema: str = Field(default="t2c_data_ingest", validation_alias="INGEST_DB_SCHEMA")
    reference_schema: str = Field(default="t2c_data", validation_alias="REFERENCE_DB_SCHEMA")
    # Operational control schema (ingestion parameters table lives here, not duplicated).
    controle_schema: str = Field(default="controle", validation_alias="CONTROLE_DB_SCHEMA")

    # Shared with t2c_data so the same JWT validates in both products. MUST match the value
    # configured in the t2c_data backend.
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    # Encrypts connection passwords at rest (Fernet). Falls back to the JWT secret in dev.
    connection_secret_key: str | None = Field(
        default=None, validation_alias="CONNECTION_SECRET_KEY"
    )

    # "direct" (default): the ingest authenticates against t2c_data.users in the shared DB
    # and mints the JWT itself (no dependency on the t2c_data backend being up).
    # "proxy": forward credentials to the t2c_data backend at T2C_DATA_AUTH_BASE_URL.
    auth_mode: str = Field(default="direct", validation_alias="AUTH_MODE")

    # URL of the t2c_data backend used only for the login proxy (issuing tokens). The ingest
    # product never stores passwords; it forwards credentials to t2c_data's /auth/login.
    t2c_data_auth_base_url: str | None = Field(
        default=None, validation_alias="T2C_DATA_AUTH_BASE_URL"
    )

    # Spark cluster (local docker by default).
    spark_master_url: str = Field(
        default="spark://spark-master:7077", validation_alias="SPARK_MASTER_URL"
    )
    spark_jobs_dir: str = Field(default="/opt/spark/jobs", validation_alias="SPARK_JOBS_DIR")
    # Driver host advertised to executors. MUST be a DNS-valid name (NO underscores — Spark
    # rejects them as "Invalid Spark URL"). Use the compose service name (e.g. "worker").
    spark_driver_host: str | None = Field(default=None, validation_alias="SPARK_DRIVER_HOST")
    spark_driver_bind_address: str | None = Field(
        default=None, validation_alias="SPARK_DRIVER_BIND_ADDRESS"
    )
    # Local JDBC jars (mounted from ./spark/jars) added to spark-submit via --jars when present.
    spark_local_jars_dir: str = Field(default="/app/jars", validation_alias="SPARK_LOCAL_JARS_DIR")
    # Maven coordinates fetched by spark-submit --packages when the JDBC jars are not local.
    spark_jdbc_packages: str = Field(
        default="org.postgresql:postgresql:42.7.10,com.mysql:mysql-connector-j:9.1.0",
        validation_alias="SPARK_JDBC_PACKAGES",
    )
    # Directories the job code viewer is allowed to read from (comma-separated). Any script
    # outside these (or path traversal) is rejected.
    allowed_script_dirs: str = Field(
        default="/opt/t2c/spark/jobs,/opt/t2c/python_jobs,/opt/spark/jobs,/app/jobs,/opt/t2c/jobs/archive",
        validation_alias="ALLOWED_SCRIPT_DIRS",
    )
    # Where deleted jobs' code is archived before soft delete (inside the project, never
    # hard-deleted). See features/jobs/archive_service.
    job_archive_dir: str = Field(
        default="/opt/t2c/jobs/archive", validation_alias="JOB_ARCHIVE_DIR"
    )
    # Versioned (git-tracked) roots where new jobs' code is provisioned, by engine. Every job's
    # code lives here so it is committed to GitHub and shipped by CI/CD (K8s) — there is no
    # unversioned scratch area.
    spark_jobs_dir: str = Field(
        default="/opt/t2c/spark/jobs", validation_alias="SPARK_JOBS_DIR"
    )
    python_jobs_dir: str = Field(
        default="/opt/t2c/python_jobs", validation_alias="PYTHON_JOBS_DIR"
    )

    @property
    def allowed_script_dirs_list(self) -> list[str]:
        return [d.strip() for d in self.allowed_script_dirs.split(",") if d.strip()]

    # Extensions the code editor may edit/save. Anything else is read-only / rejected on save.
    job_code_editable_extensions: str = Field(
        default=".py,.sql,.sh,.yaml,.yml,.json,.txt",
        validation_alias="JOB_CODE_EDITABLE_EXTENSIONS",
    )
    # Extensions never allowed for editing (secrets/keys/config).
    job_code_blocked_extensions: str = Field(
        default=".env,.pem,.key,.crt,.p12,.jks,.properties,.ini",
        validation_alias="JOB_CODE_BLOCKED_EXTENSIONS",
    )
    job_code_backup_dir: str = Field(
        default="/opt/t2c/backups/job-code", validation_alias="JOB_CODE_BACKUP_DIR"
    )

    # ── Cluster libraries (managed pip installs) ──
    # Python interpreter used to run pip. Defaults to the worker's own interpreter (empty ->
    # sys.executable at runtime). Point this at a venv (e.g. /opt/t2c/venvs/ingest/bin/python)
    # to isolate installs later without code changes.
    library_pip_python: str = Field(default="", validation_alias="LIBRARY_PIP_PYTHON")
    # Install into the per-user site (~/.local) — required when the worker runs as non-root.
    library_pip_user: bool = Field(default=True, validation_alias="LIBRARY_PIP_USER")
    library_install_timeout: int = Field(default=600, validation_alias="LIBRARY_INSTALL_TIMEOUT")

    # ── Data quality reconciliation (query source/target DBs after a run) ──
    dq_reconcile_enabled: bool = Field(default=True, validation_alias="DQ_RECONCILE_ENABLED")
    dq_reconcile_timeout: int = Field(default=8, validation_alias="DQ_RECONCILE_TIMEOUT")

    # ── Security hardening ──
    # Allow alert webhooks to target internal/private hosts (SSRF guard off). Default: block.
    alerts_allow_internal_targets: bool = Field(
        default=False, validation_alias="ALERTS_ALLOW_INTERNAL_TARGETS"
    )
    # Alert delivery retry: attempts with exponential backoff before a notification goes 'dead'.
    alert_max_attempts: int = Field(default=5, validation_alias="ALERT_MAX_ATTEMPTS")
    alert_retry_base_seconds: int = Field(default=30, validation_alias="ALERT_RETRY_BASE_SECONDS")
    # Silent-failure monitors.
    schedule_overdue_grace_seconds: int = Field(default=300, validation_alias="SCHEDULE_OVERDUE_GRACE_SECONDS")
    worker_down_threshold_seconds: int = Field(default=180, validation_alias="WORKER_DOWN_THRESHOLD_SECONDS")
    # E-mail alert channel (SMTP). Empty host disables email delivery.
    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str = Field(default="", validation_alias="SMTP_USER")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", validation_alias="SMTP_FROM")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")
    # Direct-mode login: by default users with MFA enabled must authenticate via proxy mode
    # (which performs the full MFA challenge). Set true to allow the legacy dev bypass.
    auth_allow_mfa_bypass: bool = Field(default=False, validation_alias="AUTH_ALLOW_MFA_BYPASS")
    # Login throttling (per email+IP): max failed attempts within the window before 429.
    login_max_attempts: int = Field(default=8, validation_alias="LOGIN_MAX_ATTEMPTS")
    login_window_seconds: int = Field(default=300, validation_alias="LOGIN_WINDOW_SECONDS")

    # ── Retention (append-only tables). 0 disables that table's pruning. Days. ──
    retention_execution_logs_days: int = Field(default=90, validation_alias="RETENTION_EXECUTION_LOGS_DAYS")
    retention_executions_days: int = Field(default=0, validation_alias="RETENTION_EXECUTIONS_DAYS")
    retention_schedule_runs_days: int = Field(default=90, validation_alias="RETENTION_SCHEDULE_RUNS_DAYS")
    retention_alert_notifications_days: int = Field(default=90, validation_alias="RETENTION_ALERT_NOTIFICATIONS_DAYS")
    retention_audit_days: int = Field(default=0, validation_alias="RETENTION_AUDIT_DAYS")
    retention_interval_seconds: int = Field(default=3600, validation_alias="RETENTION_INTERVAL_SECONDS")

    # ── Execution reliability ──
    # Lease TTL for a running execution; a reaper fails runs whose lease expired (worker crash).
    worker_lease_ttl_seconds: int = Field(default=120, validation_alias="WORKER_LEASE_TTL_SECONDS")
    # How often the worker refreshes the lease / checks cancel while a job runs.
    worker_heartbeat_seconds: int = Field(default=20, validation_alias="WORKER_HEARTBEAT_SECONDS")

    # ── Cluster runtime image (libraries + jobs baked into a versioned image) ──
    runtime_image_name: str = Field(default="t2c-data-ingest-spark-runtime", validation_alias="RUNTIME_IMAGE_NAME")
    runtime_base_image: str = Field(default="apache/spark:3.5.1", validation_alias="RUNTIME_BASE_IMAGE")
    # Where build contexts are written (mounted volume). The worker runs `docker build` here.
    runtime_build_context_dir: str = Field(default="/opt/t2c/runtime/builds", validation_alias="RUNTIME_BUILD_CONTEXT_DIR")
    runtime_build_timeout: int = Field(default=1800, validation_alias="RUNTIME_BUILD_TIMEOUT")
    # A running Spark container the worker uses (via `docker exec`) to spark-submit validations,
    # so the driver Python matches the executors (the runtime image). Empty disables docker exec.
    runtime_spark_submit_container: str = Field(default="", validation_alias="RUNTIME_SPARK_SUBMIT_CONTAINER")
    spark_expected_workers: int = Field(default=3, validation_alias="SPARK_EXPECTED_WORKERS")
    # Applying an active image to the local cluster: retag to this tag (used by the worker
    # services in docker-compose) and recreate these containers with the new image.
    runtime_worker_image_tag: str = Field(
        default="t2c-data-ingest-spark-runtime:local", validation_alias="RUNTIME_WORKER_IMAGE_TAG"
    )
    runtime_spark_worker_containers: str = Field(
        default="t2c-data-ingest-spark-worker-1-1,t2c-data-ingest-spark-worker-2-1,t2c-data-ingest-spark-worker-3-1",
        validation_alias="RUNTIME_SPARK_WORKER_CONTAINERS",
    )
    runtime_spark_master_webui: str = Field(
        default="http://spark-master:8080", validation_alias="RUNTIME_SPARK_MASTER_WEBUI"
    )

    @property
    def runtime_spark_worker_containers_list(self) -> list[str]:
        return [c.strip() for c in self.runtime_spark_worker_containers.split(",") if c.strip()]

    @property
    def job_code_editable_extensions_set(self) -> set[str]:
        return {e.strip().lower() for e in self.job_code_editable_extensions.split(",") if e.strip()}

    @property
    def job_code_blocked_extensions_set(self) -> set[str]:
        return {e.strip().lower() for e in self.job_code_blocked_extensions.split(",") if e.strip()}

    # Worker queue polling (the API only enqueues; heavy work runs in the worker/cluster).
    worker_poll_interval_seconds: int = 2

    # Scheduler (separate process) — checks due job_schedules and enqueues executions.
    scheduler_timezone: str = Field(
        default="America/Sao_Paulo", validation_alias="SCHEDULER_TIMEZONE"
    )
    scheduler_poll_interval_seconds: int = Field(
        default=30, validation_alias="SCHEDULER_POLL_INTERVAL_SECONDS"
    )

    cors_allow_origins: str = ""

    frontend_base_url: str | None = Field(default=None, validation_alias="FRONTEND_BASE_URL")

    allow_insecure_defaults: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_INSECURE_DEFAULTS", "allow_insecure_defaults"),
    )

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allow_origins.split(",") if item.strip()]

    @property
    def is_dev(self) -> bool:
        return is_dev_environment(self.env)

    def security_errors(self) -> list[str]:
        """Return fatal misconfigurations for a non-dev environment (empty in dev or when
        allow_insecure_defaults is explicitly set)."""
        if self.is_dev or self.allow_insecure_defaults:
            return []
        errors: list[str] = []
        weak = {"", "change-me", "change-me-must-match-t2c-data"}
        if (self.jwt_secret_key or "").strip() in weak or len((self.jwt_secret_key or "").strip()) < 32:
            errors.append("JWT_SECRET_KEY ausente/fraco (defina um segredo forte, >= 32 chars).")
        if not (self.connection_secret_key or "").strip():
            errors.append(
                "CONNECTION_SECRET_KEY ausente: a chave de criptografia em repouso não pode "
                "recair sobre o segredo do JWT. Gere uma com Fernet.generate_key()."
            )
        if self.cors_allow_origins.strip() == "*":
            errors.append("CORS_ALLOW_ORIGINS='*' não é permitido com credenciais habilitadas.")
        return errors


settings = Settings()
