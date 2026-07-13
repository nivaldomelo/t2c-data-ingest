from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from t2c_ingest.models.connection import CONNECTION_TYPES


class ConnectionBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    connection_type: str
    connection_category: str | None = None  # derivado do tipo no backend
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    schema_name: str | None = None
    extra_params: dict | None = None
    ssl_enabled: bool = False
    active: bool = True
    # Usable as source (read) and/or destination (write).
    can_read: bool = True
    can_write: bool = False

    @field_validator("connection_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in CONNECTION_TYPES:
            raise ValueError(f"connection_type deve ser um de {CONNECTION_TYPES}")
        return v


class ConnectionCreate(ConnectionBase):
    # Password is write-only; optional so a connection can be created and filled later.
    password: str | None = None
    # S3 (access_key mode) credentials — write-only, encrypted at rest, never returned.
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    # Generic type-specific secrets (API tokens, client_secret, connection strings, …), write-only.
    # Keys are declared per connector in the registry; stored in the encrypted secrets blob.
    secrets: dict[str, str] | None = None


class ConnectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    connection_type: str | None = None
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    # Empty/omitted password keeps the currently stored one.
    password: str | None = None
    schema_name: str | None = None
    extra_params: dict | None = None
    ssl_enabled: bool | None = None
    active: bool | None = None
    can_read: bool | None = None
    can_write: bool | None = None
    # Empty/omitted AWS secret keeps the currently stored one.
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    # Empty/omitted secret value keeps the currently stored one (per key).
    secrets: dict[str, str] | None = None

    @field_validator("connection_type")
    @classmethod
    def _valid_type(cls, v: str | None) -> str | None:
        if v is not None and v not in CONNECTION_TYPES:
            raise ValueError(f"connection_type deve ser um de {CONNECTION_TYPES}")
        return v


class ConnectionOut(ConnectionBase):
    """Public representation — never includes any secret, only whether one is stored."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    has_password: bool = False
    has_aws_access_key: bool = False
    has_aws_secret_key: bool = False
    has_aws_session_token: bool = False
    # Which generic secret keys are stored (names only — never the values).
    secrets_present: list[str] = []
    last_test_status: str
    last_test_message: str | None = None
    last_tested_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ConnectionTestResult(BaseModel):
    status: str  # success | failed
    message: str
    tested_at: datetime | None = None


class ConnectionSummary(BaseModel):
    total: int
    postgres: int
    mysql: int
    s3: int = 0
    # Contagem por categoria (database | storage | api).
    database: int = 0
    storage: int = 0
    api: int = 0
    test_success: int
    test_failed: int


class S3ObjectItem(BaseModel):
    key: str
    size: int | None = None
    last_modified: datetime | None = None
    storage_class: str | None = None


class S3ObjectsOut(BaseModel):
    bucket: str | None = None
    prefix: str | None = None
    items: list[S3ObjectItem] = []


class S3TestResult(BaseModel):
    success: bool
    message: str
    details: dict = {}
