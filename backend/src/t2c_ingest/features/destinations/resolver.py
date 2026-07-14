"""DestinationResolver — resolve um destino declarativo em configuração normalizada e em
env/args seguros para o runner. Nenhum segredo aqui (credenciais ficam na conexão)."""
from __future__ import annotations

from t2c_ingest.models.connection import Connection
from t2c_ingest.models.destination import Destination


def _clean_prefix(p: str | None) -> str:
    return (p or "").strip().strip("/")


def s3_path(dest: Destination) -> str:
    if dest.target_path:
        return dest.target_path
    bucket = dest.target_bucket or ""
    prefix = _clean_prefix(dest.target_prefix)
    return f"s3a://{bucket}/{prefix}/" if prefix else f"s3a://{bucket}/"


def target_display(dest: Destination) -> str:
    if dest.destination_type == "s3":
        return s3_path(dest)
    schema = dest.target_schema or ""
    table = dest.target_table or ""
    return f"{schema}.{table}".strip(".") or (table or "—")


def normalized(dest: Destination, conn: Connection | None) -> dict:
    """Config normalizada (§14) — sem segredos."""
    base = {
        "destination_id": dest.id,
        "destination_type": dest.destination_type,
        "connection_id": dest.connection_id,
        "connection_name": conn.name if conn else None,
        "write_mode": dest.write_mode,
    }
    if dest.destination_type == "s3":
        base["target"] = {
            "bucket": dest.target_bucket,
            "prefix": _clean_prefix(dest.target_prefix) or None,
            "path": s3_path(dest),
            "layer": dest.target_layer,
            "file_format": dest.file_format,
            "write_mode": dest.write_mode,
            "compression": dest.compression,
            "partition_columns": dest.partition_columns or [],
        }
    else:
        base["target"] = {
            "schema": dest.target_schema,
            "table": dest.target_table,
            "database": dest.target_database,
            "write_mode": dest.write_mode,
            "primary_key_columns": dest.primary_key_columns or [],
            "staging_schema": dest.staging_schema,
            "staging_table": dest.staging_table,
            "upsert_strategy": dest.upsert_strategy,
            "truncate_before_load": dest.truncate_before_load,
        }
    return base


def target_env(dest: Destination) -> dict[str, str]:
    """Env NÃO-secreto com a configuração do destino (as credenciais da conexão são injetadas
    à parte pelo worker). Espelha os argumentos declarativos do runner (§13)."""
    env: dict[str, str] = {"TARGET_TYPE": dest.destination_type, "WRITE_MODE": dest.write_mode or "append"}
    if dest.destination_type == "s3":
        env.update({
            "TARGET_BUCKET": dest.target_bucket or "",
            "TARGET_PREFIX": _clean_prefix(dest.target_prefix),
            "TARGET_PATH": s3_path(dest),
            "TARGET_LAYER": dest.target_layer or "",
            "FILE_FORMAT": dest.file_format or "parquet",
            "COMPRESSION": dest.compression or "",
            "PARTITION_COLUMNS": ",".join(dest.partition_columns or []),
        })
    else:
        env.update({
            "TARGET_SCHEMA": dest.target_schema or "",
            "TARGET_TABLE": dest.target_table or "",
            "TARGET_DATABASE": dest.target_database or "",
            "PRIMARY_KEY_COLUMNS": ",".join(dest.primary_key_columns or []),
            "STAGING_SCHEMA": dest.staging_schema or "",
            "STAGING_TABLE": dest.staging_table or "",
            "UPSERT_STRATEGY": dest.upsert_strategy or "",
            "TRUNCATE_BEFORE_LOAD": "true" if dest.truncate_before_load else "false",
        })
    return {k: v for k, v in env.items() if v != ""}
