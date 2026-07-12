from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from t2c_ingest.core.db import get_db
from t2c_ingest.core.pagination import PageOut, PageParams
from t2c_ingest.features.auth_bridge import permissions as perms
from t2c_ingest.features.auth_bridge.deps import CurrentUser, require_permission
from t2c_ingest.features.data_lake import service
from t2c_ingest.features.data_lake.catalog_config import resolve_catalog_config
from t2c_ingest.features.data_lake.schemas import (
    CatalogOut,
    ColumnOut,
    FileOut,
    PartitionOut,
    QueryHistoryItem,
    QueryRequest,
    QueryResultOut,
    SampleOut,
    ScanRequest,
    ScanRunOut,
    TableOut,
    TreeOut,
)
from t2c_ingest.features.data_lake.sql_guard import SqlGuardError
from t2c_ingest.models.connection import Connection
from t2c_ingest.models.data_lake import (
    DataLakeCatalog,
    DataLakeColumn,
    DataLakeFile,
    DataLakePartition,
    DataLakeQueryHistory,
    DataLakeScanRun,
    DataLakeSchema,
    DataLakeTable,
)
from t2c_ingest.services.audit import record_audit

router = APIRouter(prefix="/data-lake", tags=["data-lake"])


# ─────────────────────────────── Catálogos / conexões ───────────────────────────────

@router.get("/catalogs", response_model=list[CatalogOut])
def list_catalogs(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> list[CatalogOut]:
    rows = db.scalars(select(DataLakeCatalog).order_by(DataLakeCatalog.name)).all()
    return [CatalogOut.model_validate(r) for r in rows]


@router.get("/connections")
def catalog_connections(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> list[dict]:
    """S3 connections and whether each has the catalog enabled — used by the Data Lake picker."""
    conns = db.scalars(select(Connection).where(Connection.connection_type == "s3").order_by(Connection.name)).all()
    out = []
    for c in conns:
        cfg = resolve_catalog_config(c)
        out.append({
            "id": c.id, "name": c.name, "catalog_enabled": cfg.enabled, "catalog_mode": cfg.mode,
            "can_read": c.can_read, "active": c.active,
        })
    return out


@router.post("/catalogs/scan", response_model=ScanRunOut, status_code=status.HTTP_202_ACCEPTED)
def scan_catalog(
    payload: ScanRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_SCAN)),
) -> ScanRunOut:
    conn = db.get(Connection, payload.connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    try:
        run = service.enqueue_scan(db, conn, name=payload.name, description=payload.description,
                                   user_email=user.email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(db, action="DATA_LAKE_CATALOG_SCAN_REQUESTED", user=user,
                 entity_type="data_lake_catalog", entity_id=run.catalog_id)
    db.commit()
    db.refresh(run)
    return ScanRunOut.model_validate(run)


@router.get("/scan-runs/{run_id}", response_model=ScanRunOut)
def get_scan_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> ScanRunOut:
    run = db.get(DataLakeScanRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Execução de scan não encontrada")
    return ScanRunOut.model_validate(run)


# ─────────────────────────────── Árvore / tabelas ───────────────────────────────

@router.get("/tree", response_model=TreeOut)
def tree(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> TreeOut:
    return TreeOut(**service.build_tree(db))


@router.get("/tables", response_model=list[TableOut])
def list_tables(
    schema_id: int | None = None,
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> list[TableOut]:
    stmt = select(DataLakeTable)
    if schema_id:
        stmt = stmt.where(DataLakeTable.schema_id == schema_id)
    if q:
        stmt = stmt.where(DataLakeTable.table_name.ilike(f"%{q.strip()}%"))
    rows = db.scalars(stmt.order_by(DataLakeTable.table_name).limit(500)).all()
    return [TableOut(**service.table_detail(db, r)) for r in rows]


def _require_table(db: Session, table_id: int) -> DataLakeTable:
    t = db.get(DataLakeTable, table_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    return t


@router.get("/tables/{table_id}", response_model=TableOut)
def get_table(
    table_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> TableOut:
    t = _require_table(db, table_id)
    record_audit(db, action="DATA_LAKE_TABLE_OPENED", user=user, entity_type="data_lake_table", entity_id=t.id)
    db.commit()
    return TableOut(**service.table_detail(db, t))


@router.get("/tables/{table_id}/columns", response_model=list[ColumnOut])
def table_columns(
    table_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> list[ColumnOut]:
    _require_table(db, table_id)
    rows = db.scalars(
        select(DataLakeColumn).where(DataLakeColumn.table_id == table_id)
        .order_by(DataLakeColumn.ordinal_position)
    ).all()
    return [ColumnOut.model_validate(r) for r in rows]


@router.get("/tables/{table_id}/files", response_model=PageOut[FileOut])
def table_files(
    table_id: int,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> PageOut[FileOut]:
    _require_table(db, table_id)
    total = db.scalar(select(func.count(DataLakeFile.id)).where(DataLakeFile.table_id == table_id)) or 0
    rows = db.scalars(
        select(DataLakeFile).where(DataLakeFile.table_id == table_id)
        .order_by(desc(DataLakeFile.last_modified_at)).offset(params.offset).limit(params.limit)
    ).all()
    return PageOut.build([FileOut.model_validate(r) for r in rows], total, params)


@router.get("/tables/{table_id}/partitions", response_model=list[PartitionOut])
def table_partitions(
    table_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> list[PartitionOut]:
    _require_table(db, table_id)
    rows = db.scalars(
        select(DataLakePartition).where(DataLakePartition.table_id == table_id)
        .order_by(desc(DataLakePartition.partition_path)).limit(1000)
    ).all()
    return [PartitionOut.model_validate(r) for r in rows]


@router.get("/tables/{table_id}/sample", response_model=SampleOut)
def table_sample(
    table_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_QUERY)),
) -> SampleOut:
    """Enqueue a bounded ``SELECT * FROM <schema.table>`` sample. Poll the returned query id."""
    t = _require_table(db, table_id)
    d = service.table_detail(db, t)
    conn = db.get(Connection, d.get("connection_id"))
    if not conn:
        raise HTTPException(status_code=422, detail="Conexão do catálogo não encontrada.")
    sql = f"SELECT * FROM {d['schema_name']}.{t.table_name} LIMIT {limit}"
    row = service.enqueue_query(db, conn, sql=sql, limit=limit, table_id=t.id, user_email=user.email)
    record_audit(db, action="DATA_LAKE_SAMPLE_VIEWED", user=user, entity_type="data_lake_table", entity_id=t.id)
    db.commit()
    return SampleOut(query_id=row.id, status=row.status)


# ─────────────────────────────── Consulta rápida ───────────────────────────────

@router.post("/query", response_model=QueryResultOut, status_code=status.HTTP_202_ACCEPTED)
def run_query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_QUERY)),
) -> QueryResultOut:
    conn = db.get(Connection, payload.connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    try:
        row = service.enqueue_query(db, conn, sql=payload.sql, limit=payload.limit,
                                    table_id=payload.table_id, user_email=user.email)
    except SqlGuardError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(db, action="DATA_LAKE_QUERY_EXECUTED", user=user,
                 entity_type="data_lake_query", entity_id=row.id)
    db.commit()
    db.refresh(row)
    return _query_out(row)


@router.get("/queries/{query_id}", response_model=QueryResultOut)
def get_query(
    query_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> QueryResultOut:
    row = db.get(DataLakeQueryHistory, query_id)
    if not row:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    return _query_out(row)


@router.get("/query-history", response_model=list[QueryHistoryItem])
def query_history(
    connection_id: int | None = None,
    table_id: int | None = None,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(perms.INGEST_DATA_LAKE_READ)),
) -> list[QueryHistoryItem]:
    stmt = select(DataLakeQueryHistory)
    if connection_id:
        stmt = stmt.where(DataLakeQueryHistory.connection_id == connection_id)
    if table_id:
        stmt = stmt.where(DataLakeQueryHistory.table_id == table_id)
    rows = db.scalars(stmt.order_by(desc(DataLakeQueryHistory.id)).limit(limit)).all()
    return [QueryHistoryItem.model_validate(r) for r in rows]


def _query_out(row: DataLakeQueryHistory) -> QueryResultOut:
    preview = row.result_preview or {}
    return QueryResultOut(
        id=row.id, status=row.status, executed_sql=row.executed_sql, translated_sql=row.translated_sql,
        columns=preview.get("columns", []), rows=preview.get("rows", []),
        rows_returned=row.rows_returned, limit_applied=row.limit_applied,
        duration_seconds=row.duration_seconds, error_message=row.error_message,
        started_at=row.started_at, finished_at=row.finished_at,
    )
