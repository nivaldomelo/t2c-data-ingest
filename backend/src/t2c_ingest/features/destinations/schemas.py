from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from t2c_ingest.models.destination import DESTINATION_TYPES


class DestinationBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    destination_type: str
    connection_id: int
    # relacional
    target_schema: str | None = None
    target_table: str | None = None
    target_database: str | None = None
    # s3
    target_bucket: str | None = None
    target_prefix: str | None = None
    target_path: str | None = None
    target_layer: str | None = None
    file_format: str | None = None
    write_mode: str = "append"
    compression: str | None = None
    encryption_mode: str | None = None   # SSE-S3 | SSE-KMS
    kms_key_id: str | None = None        # não secreto
    partition_columns: list[str] | None = None
    primary_key_columns: list[str] | None = None
    staging_schema: str | None = None
    staging_table: str | None = None
    upsert_strategy: str | None = None
    truncate_before_load: bool = False
    options: dict | None = None
    is_template: bool = False
    active: bool = True

    @field_validator("destination_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in DESTINATION_TYPES:
            raise ValueError(f"destination_type deve ser um de {DESTINATION_TYPES}")
        return v


class DestinationCreate(DestinationBase):
    pass


class DestinationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    connection_id: int | None = None
    target_schema: str | None = None
    target_table: str | None = None
    target_database: str | None = None
    target_bucket: str | None = None
    target_prefix: str | None = None
    target_path: str | None = None
    target_layer: str | None = None
    file_format: str | None = None
    write_mode: str | None = None
    compression: str | None = None
    encryption_mode: str | None = None
    kms_key_id: str | None = None
    partition_columns: list[str] | None = None
    primary_key_columns: list[str] | None = None
    staging_schema: str | None = None
    staging_table: str | None = None
    upsert_strategy: str | None = None
    truncate_before_load: bool | None = None
    options: dict | None = None
    is_template: bool | None = None
    active: bool | None = None


class DestinationOut(DestinationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    connection_name: str | None = None
    connection_type: str | None = None
    target_display: str | None = None  # "spark.payments" ou "s3a://bucket/prefix/"
    last_test_status: str = "not_tested"
    last_test_message: str | None = None
    last_tested_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DestinationSummary(BaseModel):
    total: int
    postgres: int
    s3: int
    active: int
    test_failed: int


class DestinationTestResult(BaseModel):
    status: str  # success | failed
    message: str
    checks: list[dict] = []  # [{name, ok, detail}]
    tested_at: datetime | None = None
