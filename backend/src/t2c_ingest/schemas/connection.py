from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from t2c_ingest.models.connection import CONNECTION_TYPES


class ConnectionBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    connection_type: str
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    schema_name: str | None = None
    extra_params: dict | None = None
    ssl_enabled: bool = False
    active: bool = True

    @field_validator("connection_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in CONNECTION_TYPES:
            raise ValueError(f"connection_type deve ser um de {CONNECTION_TYPES}")
        return v


class ConnectionCreate(ConnectionBase):
    # Password is write-only; optional so a connection can be created and filled later.
    password: str | None = None


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

    @field_validator("connection_type")
    @classmethod
    def _valid_type(cls, v: str | None) -> str | None:
        if v is not None and v not in CONNECTION_TYPES:
            raise ValueError(f"connection_type deve ser um de {CONNECTION_TYPES}")
        return v


class ConnectionOut(ConnectionBase):
    """Public representation — never includes the password, only whether one is stored."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    has_password: bool = False
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
    test_success: int
    test_failed: int
