from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CatalogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    connection_id: int
    name: str
    description: str | None = None
    active: bool = True
    last_scan_status: str | None = None
    last_scan_at: datetime | None = None
    last_scan_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TreeTable(BaseModel):
    id: int
    name: str
    files_count: int | None = None
    total_size_bytes: int | None = None
    last_modified_at: datetime | None = None
    status: str = "active"


class TreeSchema(BaseModel):
    id: int
    name: str
    layer_name: str | None = None
    bucket_name: str
    tables: list[TreeTable] = []


class TreeCatalog(BaseModel):
    id: int
    name: str
    connection_id: int
    connection_name: str | None = None
    last_scan_status: str | None = None
    last_scan_at: datetime | None = None
    schemas: list[TreeSchema] = []


class TreeOut(BaseModel):
    catalogs: list[TreeCatalog] = []


class ColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    column_name: str
    ordinal_position: int | None = None
    spark_type: str | None = None
    parquet_type: str | None = None
    nullable: bool | None = None
    is_partition: bool = False
    comment: str | None = None


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    partition_path: str | None = None
    object_key: str
    size_bytes: int | None = None
    last_modified_at: datetime | None = None
    storage_class: str | None = None


class PartitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    partition_path: str
    partition_values: dict | None = None
    files_count: int | None = None
    total_size_bytes: int | None = None
    last_modified_at: datetime | None = None


class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    schema_id: int
    schema_name: str | None = None
    layer_name: str | None = None
    table_name: str
    full_name: str | None = None
    table_path: str
    file_format: str = "parquet"
    partition_columns: list | None = None
    columns_count: int | None = None
    files_count: int | None = None
    total_size_bytes: int | None = None
    estimated_rows: int | None = None
    last_modified_at: datetime | None = None
    last_schema_scan_at: datetime | None = None
    status: str = "active"
    connection_id: int | None = None
    bucket_name: str | None = None


class ScanRequest(BaseModel):
    connection_id: int
    name: str | None = None
    description: str | None = None


class ScanRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    catalog_id: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    stats: dict | None = None
    message: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None


class QueryRequest(BaseModel):
    connection_id: int
    sql: str = Field(min_length=1)
    limit: int | None = None
    table_id: int | None = None
    catalog_id: int | None = None


class QueryColumn(BaseModel):
    name: str
    type: str


class QueryResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    executed_sql: str
    translated_sql: str | None = None
    columns: list[QueryColumn] = []
    rows: list[dict] = []
    rows_returned: int | None = None
    limit_applied: int | None = None
    duration_seconds: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class QueryHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    connection_id: int
    table_id: int | None = None
    executed_sql: str
    status: str
    rows_returned: int | None = None
    duration_seconds: int | None = None
    error_message: str | None = None
    executed_by: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class SampleOut(BaseModel):
    columns: list[QueryColumn] = []
    rows: list[dict] = []
    rows_returned: int = 0
    query_id: int | None = None
    status: str = "success"
