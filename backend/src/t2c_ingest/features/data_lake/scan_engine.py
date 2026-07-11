"""In-process Data Lake scan (runs inside the worker).

Lists schemas/tables/files/partitions with boto3 and infers the Parquet schema by reading only
the file FOOTER via pyarrow (range reads — no full download, no Spark, no JVM). This keeps the
scan lightweight and reliable on constrained hosts while honoring "scan runs in the worker".
"""
from __future__ import annotations

from urllib.parse import urlparse

from t2c_ingest.features.connections import s3_service
from t2c_ingest.features.data_lake.catalog_config import CatalogConfig

MAX_TABLES_PER_SCHEMA = 500
MAX_FILES_PER_TABLE = 2000        # walked for metrics
MAX_FILES_EMITTED = 200           # persisted (recent sample)
MAX_PARTITIONS_EMITTED = 500
PARQUET_EXT = (".parquet", ".parq")

# Arrow type -> Spark-style simpleString (best effort; unknowns fall back to str()).
_ARROW_SPARK = {
    "int64": "bigint", "int32": "int", "int16": "smallint", "int8": "tinyint",
    "uint64": "bigint", "uint32": "bigint", "uint16": "int", "uint8": "smallint",
    "double": "double", "float": "float", "halffloat": "float",
    "string": "string", "large_string": "string", "bool": "boolean",
    "date32[day]": "date", "date64[ms]": "date", "binary": "binary", "large_binary": "binary",
}


def _spark_type(arrow_type) -> str:
    s = str(arrow_type)
    if s in _ARROW_SPARK:
        return _ARROW_SPARK[s]
    if s.startswith("timestamp"):
        return "timestamp"
    if s.startswith("decimal"):
        return s.replace("decimal128", "decimal").replace("decimal256", "decimal")
    if s.startswith("list"):
        return "array"
    if s.startswith("struct"):
        return "struct"
    return s


def _pa_filesystem(conn):
    """Build a pyarrow S3FileSystem for the connection (MinIO/AWS)."""
    import pyarrow.fs as pafs

    cfg = s3_service.s3_settings(conn)
    creds = s3_service.resolve_aws_credentials(conn)
    kw: dict = {}
    if cfg.region:
        kw["region"] = cfg.region
    if creds.get("aws_access_key_id"):
        kw["access_key"] = creds["aws_access_key_id"]
        kw["secret_key"] = creds.get("aws_secret_access_key")
        if creds.get("aws_session_token"):
            kw["session_token"] = creds["aws_session_token"]
    if cfg.endpoint_url:
        parsed = urlparse(cfg.endpoint_url)
        kw["endpoint_override"] = parsed.netloc or parsed.path
        kw["scheme"] = parsed.scheme or ("https" if cfg.ssl_enabled else "http")
    return pafs.S3FileSystem(**kw)


def _list_dirs(s3, bucket: str, prefix: str) -> list[str]:
    prefix = (prefix or "").strip("/")
    pfx = f"{prefix}/" if prefix else ""
    out: list[str] = []
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": pfx, "Delimiter": "/", "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        for cp in resp.get("CommonPrefixes", []):
            name = cp["Prefix"][len(pfx):].strip("/")
            if name and not name.startswith("_") and not name.startswith("."):
                out.append(name)
        if not resp.get("IsTruncated") or len(out) >= MAX_TABLES_PER_SCHEMA:
            break
        token = resp.get("NextContinuationToken")
    return out[:MAX_TABLES_PER_SCHEMA]


def _scan_table_files(s3, bucket: str, table_prefix: str) -> dict:
    table_prefix = table_prefix.strip("/") + "/"
    files: list[dict] = []
    part_agg: dict[str, dict] = {}
    total_size = 0
    scanned = 0
    last_modified = None
    newest_key = None
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": table_prefix, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            base = key.rsplit("/", 1)[-1]
            if key.endswith("/") or base.startswith("_") or base.startswith("."):
                continue
            if not key.lower().endswith(PARQUET_EXT):
                continue
            scanned += 1
            size = int(obj.get("Size", 0) or 0)
            total_size += size
            lm = obj.get("LastModified")
            lm_iso = lm.isoformat() if lm else None
            if lm_iso and (last_modified is None or lm_iso > last_modified):
                last_modified = lm_iso
                newest_key = key
            rel = key[len(table_prefix):]
            part_path = rel.rsplit("/", 1)[0] if "/" in rel else ""
            agg = part_agg.setdefault(part_path, {"files_count": 0, "total_size_bytes": 0, "last_modified_at": None})
            agg["files_count"] += 1
            agg["total_size_bytes"] += size
            if lm_iso and (agg["last_modified_at"] is None or lm_iso > agg["last_modified_at"]):
                agg["last_modified_at"] = lm_iso
            if len(files) < MAX_FILES_EMITTED:
                files.append({
                    "object_key": key, "partition_path": part_path or None, "size_bytes": size,
                    "last_modified_at": lm_iso, "storage_class": obj.get("StorageClass"),
                    "etag": (obj.get("ETag") or "").strip('"') or None,
                })
        if not resp.get("IsTruncated") or scanned >= MAX_FILES_PER_TABLE:
            break
        token = resp.get("NextContinuationToken")

    partitions = []
    for pth, agg in list(part_agg.items())[:MAX_PARTITIONS_EMITTED]:
        if not pth:
            continue
        values = {}
        for seg in pth.split("/"):
            if "=" in seg:
                k, v = seg.split("=", 1)
                values[k] = v
        partitions.append({
            "partition_path": pth, "partition_values": values or None,
            "files_count": agg["files_count"], "total_size_bytes": agg["total_size_bytes"],
            "last_modified_at": agg["last_modified_at"],
        })
    part_cols: list[str] = []
    for p in partitions:
        for k in (p["partition_values"] or {}):
            if k not in part_cols:
                part_cols.append(k)
    return {
        "files": files, "partitions": partitions, "partition_columns": part_cols,
        "files_count": scanned, "total_size_bytes": total_size,
        "last_modified_at": last_modified, "newest_key": newest_key,
    }


def _infer_columns(fs, bucket: str, key: str, partition_cols: list[str]) -> list[dict]:
    """Read the Parquet footer of ``key`` (range reads) and return columns + partition columns."""
    import pyarrow.parquet as pq

    cols: list[dict] = []
    if key:
        try:
            with fs.open_input_file(f"{bucket}/{key}") as f:
                schema = pq.read_schema(f)
            for field in schema:
                cols.append({
                    "name": field.name, "spark_type": _spark_type(field.type),
                    "parquet_type": str(field.type), "nullable": bool(field.nullable),
                    "is_partition": False,
                })
        except Exception:  # noqa: BLE001 - unreadable footer -> only partition columns
            cols = []
    existing = {c["name"] for c in cols}
    for pc in partition_cols:
        if pc not in existing:
            cols.append({"name": pc, "spark_type": "string", "parquet_type": "string",
                         "nullable": True, "is_partition": True})
    return cols


def scan_catalog(conn, cfg: CatalogConfig) -> dict:
    """Scan the whole catalog; returns {"schemas": [...]} in the shape service._persist_scan expects."""
    s3 = s3_service.build_client(conn)
    fs = _pa_filesystem(conn)

    specs = []
    if cfg.mode == "prefix_as_schema" and cfg.root:
        bucket, base = cfg.root.bucket, cfg.root.base_prefix
        for sname in _list_dirs(s3, bucket, base):
            sp = f"{base}/{sname}".strip("/") if base else sname
            specs.append({"name": sname, "layer_name": sname, "bucket": bucket, "base_prefix": sp})
    else:
        for layer in cfg.layers:
            specs.append({"name": layer.name, "layer_name": layer.layer_name or layer.name,
                          "bucket": layer.bucket, "base_prefix": layer.base_prefix})

    schemas_out = []
    for spec in specs:
        bucket, base = spec["bucket"], spec["base_prefix"]
        tables = []
        for tname in _list_dirs(s3, bucket, base):
            tprefix = f"{base}/{tname}".strip("/") if base else tname
            info = _scan_table_files(s3, bucket, tprefix)
            columns = (
                _infer_columns(fs, bucket, info["newest_key"], info["partition_columns"])
                if info["files_count"] else []
            )
            tables.append({
                "name": tname, "path": f"s3a://{bucket}/{tprefix}/", "file_format": cfg.default_file_format,
                "partition_columns": info["partition_columns"], "columns_count": len(columns),
                "columns": columns, "files_count": info["files_count"],
                "total_size_bytes": info["total_size_bytes"], "last_modified_at": info["last_modified_at"],
                "files": info["files"], "partitions": info["partitions"],
            })
        schemas_out.append({"name": spec["name"], "layer_name": spec["layer_name"],
                            "bucket": bucket, "base_prefix": base, "tables": tables})
    return {"schemas": schemas_out}
