"""Data Lake catalog service.

Two sides:
  * API side (in the web process): read the catalog, and ENQUEUE scan/query rows (status
    'queued'). No S3/Spark work happens in the web process.
  * Worker side (run_scan/run_query): claimed by the worker orchestration; runs a baked Spark
    script via ``docker exec`` into the Spark container, injecting the connection's AWS creds
    ONLY via env (never on the command line), parses a stdout JSON marker, and persists results.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.core.log_masking import mask_secrets
from t2c_ingest.features.connections import s3_service
from t2c_ingest.features.data_lake import sql_guard
from t2c_ingest.features.data_lake.catalog_config import (
    CatalogConfig,
    resolve_catalog_config,
)
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

QUERY_MARKER = "DATALAKE_QUERY_JSON:"
_QUERY_SCRIPT = "/opt/t2c/spark/jobs/system/data_lake_query.py"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db: Session, action: str, entity_type: str, entity_id, detail: dict | None = None) -> None:
    """Worker-side audit (no request context). Best-effort — never breaks the job."""
    from t2c_ingest.models.audit import AuditEvent
    try:
        db.add(AuditEvent(action=action, entity_type=entity_type, entity_id=str(entity_id),
                          detail=detail or {}))
        db.flush()
    except Exception:  # noqa: BLE001
        db.rollback()


# ─────────────────────────────── API side: read ───────────────────────────────

def build_tree(db: Session) -> dict:
    """Assemble the explorer tree (catalogs → schemas → tables) from the catalog tables."""
    catalogs = db.scalars(select(DataLakeCatalog).order_by(DataLakeCatalog.name)).all()
    conn_names = dict(db.execute(select(Connection.id, Connection.name)).all())
    schemas = db.scalars(select(DataLakeSchema).order_by(DataLakeSchema.schema_name)).all()
    tables = db.scalars(select(DataLakeTable).order_by(DataLakeTable.table_name)).all()
    by_schema: dict[int, list] = {}
    for t in tables:
        by_schema.setdefault(t.schema_id, []).append(t)
    schemas_by_cat: dict[int, list] = {}
    for s in schemas:
        schemas_by_cat.setdefault(s.catalog_id, []).append(s)

    out = []
    for c in catalogs:
        out.append({
            "id": c.id, "name": c.name, "connection_id": c.connection_id,
            "connection_name": conn_names.get(c.connection_id),
            "last_scan_status": c.last_scan_status, "last_scan_at": c.last_scan_at,
            "schemas": [
                {
                    "id": s.id, "name": s.schema_name, "layer_name": s.layer_name,
                    "bucket_name": s.bucket_name,
                    "tables": [
                        {
                            "id": t.id, "name": t.table_name, "files_count": t.files_count,
                            "total_size_bytes": t.total_size_bytes,
                            "last_modified_at": t.last_modified_at, "status": t.status,
                        }
                        for t in sorted(by_schema.get(s.id, []), key=lambda x: x.table_name)
                    ],
                }
                for s in sorted(schemas_by_cat.get(c.id, []), key=lambda x: x.schema_name)
            ],
        })
    return {"catalogs": out}


def table_detail(db: Session, table: DataLakeTable) -> dict:
    schema = db.get(DataLakeSchema, table.schema_id)
    catalog = db.get(DataLakeCatalog, schema.catalog_id) if schema else None
    full = f"{schema.schema_name}.{table.table_name}" if schema else table.table_name
    d = {c.name: getattr(table, c.name) for c in table.__table__.columns}
    # Última partição (mais recente por data de modificação, depois pelo path).
    latest = db.scalar(
        select(DataLakePartition).where(DataLakePartition.table_id == table.id)
        .order_by(DataLakePartition.last_modified_at.desc().nullslast(),
                  DataLakePartition.partition_path.desc())
        .limit(1)
    )
    latest_partition = None
    if latest:
        latest_partition = {
            "path": latest.partition_path, "files_count": latest.files_count,
            "total_size_bytes": latest.total_size_bytes, "last_modified_at": latest.last_modified_at,
        }
    d.update({
        "schema_name": schema.schema_name if schema else None,
        "layer_name": schema.layer_name if schema else None,
        "full_name": full,
        "connection_id": catalog.connection_id if catalog else None,
        "connection_name": (db.scalar(select(Connection.name).where(Connection.id == catalog.connection_id)) if catalog else None),
        "bucket_name": schema.bucket_name if schema else None,
        "base_prefix": schema.base_prefix if schema else None,
        "last_catalog_scan_at": catalog.last_scan_at if catalog else None,
        "latest_partition": latest_partition,
        # Origem operacional e qualidade: estrutura presente; preenchida quando houver metadado
        # vinculável (sem link confiável tabela->job/DQ hoje -> nulos, UI mostra "não vinculado").
        "last_ingestion": {"job_name": None, "pipeline_name": None, "status": None,
                           "records_written": None, "executed_at": None},
        "quality": {"last_status": None, "score": None, "validated_at": None},
    })
    return d


# ─────────────────────────────── API side: enqueue ───────────────────────────────

def _require_catalog_connection(conn: Connection) -> CatalogConfig:
    if conn.connection_type != "s3":
        raise ValueError("A conexão precisa ser do tipo S3 / Data Lake.")
    cfg = resolve_catalog_config(conn)
    if not cfg.enabled:
        raise ValueError(
            "Catálogo não habilitado nesta conexão. Ative 'catalog_enabled' nos parâmetros da conexão S3."
        )
    if cfg.mode == "layer_as_schema" and not cfg.layers:
        raise ValueError("Nenhuma camada/schema configurada para o catálogo.")
    if cfg.mode == "prefix_as_schema" and (not cfg.root or not cfg.root.bucket):
        raise ValueError("Configuração de catálogo (prefix_as_schema) sem bucket.")
    return cfg


def get_or_create_catalog(db: Session, conn: Connection, *, name: str | None, description: str | None,
                          user_email: str | None) -> DataLakeCatalog:
    catalog = db.scalar(select(DataLakeCatalog).where(DataLakeCatalog.connection_id == conn.id))
    if catalog is None:
        catalog = DataLakeCatalog(
            connection_id=conn.id, name=(name or f"Catálogo {conn.name}"),
            description=description, created_by=user_email, updated_by=user_email,
        )
        db.add(catalog)
        db.flush()
    else:
        if name:
            catalog.name = name
        if description is not None:
            catalog.description = description
        catalog.updated_by = user_email
    return catalog


def enqueue_scan(db: Session, conn: Connection, *, name: str | None, description: str | None,
                 user_email: str | None) -> DataLakeScanRun:
    _require_catalog_connection(conn)
    catalog = get_or_create_catalog(db, conn, name=name, description=description, user_email=user_email)
    catalog.last_scan_status = "queued"
    catalog.last_scan_message = None
    run = DataLakeScanRun(catalog_id=catalog.id, status="queued", requested_by=user_email)
    db.add(run)
    db.flush()
    return run


def known_view_names(db: Session, connection_id: int) -> dict[str, str]:
    """Map ``schema__table`` -> s3a path for every table of the connection's catalog(s)."""
    cats = db.scalars(select(DataLakeCatalog.id).where(DataLakeCatalog.connection_id == connection_id)).all()
    if not cats:
        return {}
    schemas = db.scalars(select(DataLakeSchema).where(DataLakeSchema.catalog_id.in_(cats))).all()
    sid_to_name = {s.id: s.schema_name for s in schemas}
    tables = db.scalars(select(DataLakeTable).where(DataLakeTable.schema_id.in_(list(sid_to_name)))).all() if sid_to_name else []
    views = {}
    for t in tables:
        sname = sid_to_name.get(t.schema_id)
        if sname:
            views[f"{sname}__{t.table_name}"] = t.table_path
    return views


def enqueue_query(db: Session, conn: Connection, *, sql: str, limit: int | None,
                  table_id: int | None, user_email: str | None) -> DataLakeQueryHistory:
    if conn.connection_type != "s3":
        raise ValueError("A conexão precisa ser do tipo S3 / Data Lake.")
    stmt = sql_guard.validate_read_only(sql)                       # raises SqlGuardError
    views = known_view_names(db, conn.id)
    translated = sql_guard.translate_logical_names(stmt, set(views))
    translated, eff_limit = sql_guard.apply_limit(translated, limit)
    catalog = db.scalar(select(DataLakeCatalog).where(DataLakeCatalog.connection_id == conn.id))
    row = DataLakeQueryHistory(
        connection_id=conn.id, catalog_id=(catalog.id if catalog else None), table_id=table_id,
        executed_sql=sql.strip(), translated_sql=translated, limit_applied=eff_limit,
        status="queued", executed_by=user_email,
    )
    db.add(row)
    db.flush()
    return row


# ─────────────────────────── Worker side: S3 exec helpers ───────────────────────────

def _s3_exec(conn: Connection) -> tuple[dict, list[str], list[str]]:
    """Return (env, spark_confs, secret_values) to run a Spark job against this S3 connection.

    Credentials go ONLY into env (forwarded via ``docker exec -e``), never on the command line.
    """
    cfg = s3_service.s3_settings(conn)
    creds = s3_service.resolve_aws_credentials(conn)
    env: dict[str, str] = {}
    confs: list[str] = []
    secrets: list[str] = []
    ak = creds.get("aws_access_key_id")
    if ak:
        env["AWS_ACCESS_KEY_ID"] = ak
        env["AWS_SECRET_ACCESS_KEY"] = creds.get("aws_secret_access_key", "")
        secrets += [ak, creds.get("aws_secret_access_key", "")]
        if creds.get("aws_session_token"):
            env["AWS_SESSION_TOKEN"] = creds["aws_session_token"]
            secrets.append(creds["aws_session_token"])
    if cfg.region:
        env["AWS_REGION"] = env["AWS_DEFAULT_REGION"] = cfg.region
        confs.append(f"spark.hadoop.fs.s3a.endpoint.region={cfg.region}")
    if cfg.endpoint_url:
        env["AWS_ENDPOINT_URL_S3"] = cfg.endpoint_url
        confs += [
            f"spark.hadoop.fs.s3a.endpoint={cfg.endpoint_url}",
            "spark.hadoop.fs.s3a.path.style.access=true",
            f"spark.hadoop.fs.s3a.connection.ssl.enabled={'true' if cfg.ssl_enabled else 'false'}",
        ]
    return env, confs, [s for s in secrets if s]


def _spark_submit(script: str, argv: list[str], env: dict, confs: list[str], marker: str,
                  timeout: int) -> tuple[str, dict | None]:
    """docker exec spark-submit a baked script; return (masked_logs, parsed_json_or_None)."""
    import shlex

    container = settings.runtime_spark_submit_container
    conf_str = " ".join(f"--conf {shlex.quote(c)}" for c in confs)
    argv_str = " ".join(shlex.quote(a) for a in argv)
    # Quick queries run in Spark LOCAL mode (single JVM): light, fast to start, no dependency on
    # cluster capacity — appropriate for a bounded read-only sample. s3a jars are baked in.
    submit = (
        "/opt/spark/bin/spark-submit"
        " --master 'local[1]'"
        " --conf spark.pyspark.python=/usr/bin/python3"
        " --conf spark.ui.enabled=false"
        f" --driver-memory {shlex.quote(settings.data_lake_query_driver_memory)}"
        f" {conf_str} {shlex.quote(script)} {argv_str}"
    )
    exec_env = []
    for k in env:
        exec_env += ["-e", k]  # forward value from our env; keeps secrets off the cmdline
    cmd = ["docker", "exec", *exec_env, container, "bash", "-lc", submit]
    import os
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, **env})
    combined = f"{proc.stdout}\n{proc.stderr}"
    parsed = None
    for line in combined.splitlines():
        idx = line.find(marker)
        if idx != -1:
            try:
                parsed = json.loads(line[idx + len(marker):].strip())
            except json.JSONDecodeError:
                parsed = None
    return combined, parsed


# ─────────────────────────────── Worker side: run ───────────────────────────────

def run_scan(db: Session, run: DataLakeScanRun) -> None:
    """Execute a catalog scan (boto3 listing + Spark schema inference) and persist the results."""
    run.status = "running"
    run.started_at = _now()
    _audit(db, "DATA_LAKE_CATALOG_SCAN_STARTED", "data_lake_catalog", run.catalog_id)
    db.commit()
    started = time.monotonic()
    catalog = db.get(DataLakeCatalog, run.catalog_id)
    conn = db.get(Connection, catalog.connection_id) if catalog else None
    if not catalog or not conn:
        run.status = "failed"; run.error_message = "Catálogo ou conexão ausente."; run.finished_at = _now()
        db.commit(); return
    catalog.last_scan_status = "running"
    db.commit()

    try:
        from t2c_ingest.features.data_lake import scan_engine

        cfg = _require_catalog_connection(conn)
        # Listing + Parquet-footer schema inference run IN-PROCESS (boto3 + pyarrow, no Spark/JVM):
        # lightweight and reliable; reads only file footers via range requests.
        parsed = scan_engine.scan_catalog(conn, cfg)
        stats = _persist_scan(db, catalog, parsed)
        run.stats = stats
        run.status = "success"
        run.message = f"{stats['schemas']} schemas, {stats['tables']} tabelas, {stats['files']} arquivos."
        catalog.last_scan_status = "success"
        catalog.last_scan_message = run.message
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        catalog.last_scan_status = "failed"
        catalog.last_scan_message = str(exc)[:1000]
    run.finished_at = _now()
    run.duration_seconds = int(time.monotonic() - started)
    catalog.last_scan_at = run.finished_at
    _audit(db, "DATA_LAKE_CATALOG_SCAN_SUCCEEDED" if run.status == "success" else "DATA_LAKE_CATALOG_SCAN_FAILED",
           "data_lake_catalog", run.catalog_id, {"stats": run.stats} if run.stats else None)
    db.commit()


def _schema_hash(columns: list[dict]) -> str:
    """Hash determinístico do schema (nome/tipo/partição de cada coluna) p/ detectar mudança."""
    import hashlib
    sig = ";".join(
        f"{c.get('name')}:{c.get('spark_type') or c.get('type')}:{int(bool(c.get('is_partition')))}"
        for c in columns
    )
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()[:16]


def _previous_schema_hashes(db: Session, schema_ids: list[int]) -> dict[str, str]:
    """Hash anterior de cada tabela (chave ``schema_name.table_name``) antes do rescan, p/ SCHEMA_CHANGED."""
    if not schema_ids:
        return {}
    rows = db.execute(
        select(DataLakeSchema.schema_name, DataLakeTable.id, DataLakeTable.table_name,
               DataLakeColumn.column_name, DataLakeColumn.spark_type, DataLakeColumn.is_partition)
        .join(DataLakeTable, DataLakeTable.schema_id == DataLakeSchema.id)
        .join(DataLakeColumn, DataLakeColumn.table_id == DataLakeTable.id, isouter=True)
        .where(DataLakeSchema.id.in_(schema_ids))
        .order_by(DataLakeTable.id, DataLakeColumn.ordinal_position)
    ).all()
    by_table: dict[str, list[dict]] = {}
    for sname, _tid, tname, cname, stype, is_part in rows:
        if cname is None:
            continue
        by_table.setdefault(f"{sname}.{tname}", []).append(
            {"name": cname, "spark_type": stype, "is_partition": is_part})
    return {full: _schema_hash(cols) for full, cols in by_table.items()}


def _persist_scan(db: Session, catalog: DataLakeCatalog, parsed: dict) -> dict:
    """Replace the catalog's schemas/tables/columns/files/partitions with the scan result."""
    # Wipe existing catalog contents (idempotent re-scan).
    old_schemas = db.scalars(select(DataLakeSchema.id).where(DataLakeSchema.catalog_id == catalog.id)).all()
    prev_hashes = _previous_schema_hashes(db, list(old_schemas))
    if old_schemas:
        old_tables = db.scalars(select(DataLakeTable.id).where(DataLakeTable.schema_id.in_(old_schemas))).all()
        if old_tables:
            for model in (DataLakeColumn, DataLakeFile, DataLakePartition):
                db.query(model).filter(model.table_id.in_(old_tables)).delete(synchronize_session=False)
            db.query(DataLakeTable).filter(DataLakeTable.id.in_(old_tables)).delete(synchronize_session=False)
        db.query(DataLakeSchema).filter(DataLakeSchema.id.in_(old_schemas)).delete(synchronize_session=False)
    db.flush()

    n_schemas = n_tables = n_files = n_parts = 0
    for s in parsed.get("schemas", []):
        schema = DataLakeSchema(
            catalog_id=catalog.id, schema_name=s["name"], layer_name=s.get("layer_name"),
            bucket_name=s.get("bucket", ""), base_prefix=s.get("base_prefix", ""),
        )
        db.add(schema); db.flush(); n_schemas += 1
        for t in s.get("tables", []):
            table = DataLakeTable(
                schema_id=schema.id, table_name=t["name"], table_path=t["path"],
                file_format=t.get("file_format", "parquet"),
                partition_columns=t.get("partition_columns"),
                columns_count=t.get("columns_count"), files_count=t.get("files_count"),
                total_size_bytes=t.get("total_size_bytes"), estimated_rows=t.get("estimated_rows"),
                last_modified_at=_dt(t.get("last_modified_at")),
                last_schema_scan_at=_now(),
            )
            db.add(table); db.flush(); n_tables += 1
            for i, col in enumerate(t.get("columns", [])):
                db.add(DataLakeColumn(
                    table_id=table.id, column_name=col["name"], ordinal_position=i,
                    spark_type=col.get("spark_type"), parquet_type=col.get("parquet_type"),
                    nullable=col.get("nullable"), is_partition=col.get("is_partition", False),
                ))
            for f in t.get("files", []):
                db.add(DataLakeFile(
                    table_id=table.id, partition_path=f.get("partition_path"),
                    object_key=f["object_key"], size_bytes=f.get("size_bytes"),
                    last_modified_at=_dt(f.get("last_modified_at")),
                    storage_class=f.get("storage_class"), etag=f.get("etag"),
                )); n_files += 1
            for p in t.get("partitions", []):
                db.add(DataLakePartition(
                    table_id=table.id, partition_path=p["partition_path"],
                    partition_values=p.get("partition_values"), files_count=p.get("files_count"),
                    total_size_bytes=p.get("total_size_bytes"),
                    last_modified_at=_dt(p.get("last_modified_at")),
                )); n_parts += 1
            # Integração com t2c_data (ponto 16): schema/colunas descobertas (+ SCHEMA_CHANGED se o
            # hash mudou). Idempotente por (tabela, hash): rescans idênticos não duplicam eventos.
            _publish_schema_event(db, s, t, prev_hashes)
    db.flush()
    return {"schemas": n_schemas, "tables": n_tables, "files": n_files, "partitions": n_parts}


def _publish_schema_event(db: Session, s: dict, t: dict, prev_hashes: dict[str, str]) -> None:
    """Enfileira SCHEMA_DISCOVERED/COLUMNS_DISCOVERED/SCHEMA_CHANGED de uma tabela do catálogo."""
    try:
        from t2c_ingest.features.integration import service as integration
        cols = t.get("columns", []) or []
        layer = s.get("layer_name") or s.get("name")
        full_name = f"{layer}.{t['name']}" if layer else t["name"]
        new_hash = _schema_hash(cols)
        integration.publish_schema_events(
            db, table_id=full_name, table_name=t["name"], full_name=full_name, layer=layer,
            target_type="s3", bucket=s.get("bucket", ""), path=t.get("path", ""),
            file_format=t.get("file_format", "parquet"), columns=cols,
            partition_columns=t.get("partition_columns"), schema_hash=new_hash,
            previous_hash=prev_hashes.get(full_name), discovered_at=_now().isoformat())
    except Exception as exc:  # noqa: BLE001 - integração nunca quebra o scan
        print(f"[data_lake] schema event skipped: {exc}")


def run_query(db: Session, row: DataLakeQueryHistory) -> None:
    """Execute a validated read-only query via Spark and store a bounded result preview."""
    row.status = "running"
    row.started_at = _now()
    db.commit()
    started = time.monotonic()
    conn = db.get(Connection, row.connection_id)
    if not conn:
        row.status = "failed"; row.error_message = "Conexão ausente."; row.finished_at = _now(); db.commit(); return
    try:
        env, confs, secrets = _s3_exec(conn)
        views = known_view_names(db, conn.id)
        env["DATALAKE_VIEWS_JSON"] = json.dumps(views)
        argv = ["--sql", row.translated_sql or row.executed_sql, "--limit", str(row.limit_applied or sql_guard.DEFAULT_LIMIT)]
        logs, parsed = _spark_submit(
            _QUERY_SCRIPT, argv, env, confs, QUERY_MARKER, settings.data_lake_query_timeout,
        )
        logs = mask_secrets(logs, secrets)
        if parsed is None:
            raise RuntimeError("Não foi possível interpretar o resultado da consulta (marcador ausente).")
        if parsed.get("status") != "success":
            raise RuntimeError(parsed.get("error") or "Falha na execução da consulta.")
        row.result_preview = {"columns": parsed.get("columns", []), "rows": parsed.get("rows", [])}
        row.rows_returned = parsed.get("rows_returned", len(parsed.get("rows", [])))
        row.status = "success"
    except Exception as exc:  # noqa: BLE001
        row.status = "failed"
        row.error_message = str(exc)[:2000]
    row.finished_at = _now()
    row.duration_seconds = int(time.monotonic() - started)
    if row.status == "failed":
        _audit(db, "DATA_LAKE_QUERY_FAILED", "data_lake_query", row.id, {"error": row.error_message})
    db.commit()


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
