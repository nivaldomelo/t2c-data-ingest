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

    # Worker queue polling (the API only enqueues; heavy work runs in the worker/cluster).
    worker_poll_interval_seconds: int = 2

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


settings = Settings()
