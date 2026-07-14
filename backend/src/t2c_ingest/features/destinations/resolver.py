"""DestinationResolver — resolve um destino declarativo em configuração normalizada e em
env/args seguros para o runner. Nenhum segredo aqui (credenciais ficam na conexão).

Destinos TEMPLATE (is_template) padronizam o COMO e a RAIZ do destino; o nome da tabela / último
trecho do path vem em runtime (Controle de Ingestão nome_tabela ou arg do job), com suporte a
placeholder {table} (ou {nome_tabela}). Assim um punhado de destinos serve N tabelas.
"""
from __future__ import annotations

from t2c_ingest.models.connection import Connection
from t2c_ingest.models.destination import Destination


def _clean_prefix(p: str | None) -> str:
    return (p or "").strip().strip("/")


def _sub(val: str | None, table: str | None) -> str | None:
    if not val or not table:
        return val
    return val.replace("{table}", table).replace("{nome_tabela}", table)


def _has_placeholder(val: str | None) -> bool:
    return bool(val) and ("{table}" in val or "{nome_tabela}" in val)


def effective(dest: Destination, table: str | None = None) -> dict:
    """Valores concretos do destino para uma tabela em runtime (aplica template/placeholder)."""
    tbl = (table or "").strip()
    if dest.destination_type == "s3":
        base = _clean_prefix(dest.target_prefix)
        if _has_placeholder(base):
            prefix = _clean_prefix(_sub(base, tbl))
        elif dest.is_template and tbl:
            prefix = _clean_prefix(f"{base}/{tbl}" if base else tbl)
        else:
            prefix = base
        # target_path fixo só vale para destino específico sem placeholder.
        if dest.target_path and not dest.is_template and not _has_placeholder(dest.target_path):
            path = dest.target_path
        else:
            path = _sub(dest.target_path, tbl) if _has_placeholder(dest.target_path) else (
                f"s3a://{dest.target_bucket}/{prefix}/" if prefix else f"s3a://{dest.target_bucket}/"
            )
        return {"prefix": prefix, "path": path, "table": None, "staging_table": None}
    # relacional
    if _has_placeholder(dest.target_table):
        tname = _sub(dest.target_table, tbl)
    elif dest.target_table:
        tname = dest.target_table
    else:
        tname = tbl or None  # template: usa a tabela do runtime
    if _has_placeholder(dest.staging_table):
        stg = _sub(dest.staging_table, tbl)
    elif dest.staging_table:
        stg = dest.staging_table
    elif dest.is_template and dest.write_mode == "upsert" and tbl:
        stg = f"stg_{tbl}"  # convenção padrão para template
    else:
        stg = None
    return {"prefix": None, "path": None, "table": tname, "staging_table": stg}


def s3_path(dest: Destination, table: str | None = None) -> str:
    return effective(dest, table)["path"] or ""


def target_display(dest: Destination, table: str | None = None) -> str:
    # Sem tabela num destino template, mostra o placeholder para deixar o padrão explícito.
    tbl = table or ("{table}" if dest.is_template else None)
    eff = effective(dest, tbl)
    if dest.destination_type == "s3":
        return eff["path"]
    schema = dest.target_schema or ""
    return f"{schema}.{eff['table'] or ''}".strip(".") or (eff["table"] or "—")


def normalized(dest: Destination, conn: Connection | None, table: str | None = None) -> dict:
    """Config normalizada (§14) — sem segredos. Aplica a tabela de runtime quando informada."""
    eff = effective(dest, table)
    base = {
        "destination_id": dest.id,
        "destination_type": dest.destination_type,
        "connection_id": dest.connection_id,
        "connection_name": conn.name if conn else None,
        "is_template": dest.is_template,
        "runtime_table": table,
        "write_mode": dest.write_mode,
    }
    if dest.destination_type == "s3":
        base["target"] = {
            "bucket": dest.target_bucket,
            "prefix": eff["prefix"] or None,
            "path": eff["path"],
            "layer": dest.target_layer,
            "file_format": dest.file_format,
            "write_mode": dest.write_mode,
            "compression": dest.compression,
            "partition_columns": dest.partition_columns or [],
        }
    else:
        base["target"] = {
            "schema": dest.target_schema,
            "table": eff["table"],
            "database": dest.target_database,
            "write_mode": dest.write_mode,
            "primary_key_columns": dest.primary_key_columns or [],
            "staging_schema": dest.staging_schema,
            "staging_table": eff["staging_table"],
            "upsert_strategy": dest.upsert_strategy,
            "truncate_before_load": dest.truncate_before_load,
        }
    return base


def target_env(dest: Destination, table: str | None = None) -> dict[str, str]:
    """Env NÃO-secreto com a configuração do destino (credenciais da conexão são injetadas à
    parte). Aplica a tabela de runtime (template/placeholder) quando informada."""
    eff = effective(dest, table)
    env: dict[str, str] = {"TARGET_TYPE": dest.destination_type, "WRITE_MODE": dest.write_mode or "append"}
    if dest.destination_type == "s3":
        env.update({
            "TARGET_BUCKET": dest.target_bucket or "",
            "TARGET_PREFIX": eff["prefix"] or "",
            "TARGET_PATH": eff["path"] or "",
            "TARGET_LAYER": dest.target_layer or "",
            "FILE_FORMAT": dest.file_format or "parquet",
            "COMPRESSION": dest.compression or "",
            "PARTITION_COLUMNS": ",".join(dest.partition_columns or []),
        })
    else:
        env.update({
            "TARGET_SCHEMA": dest.target_schema or "",
            "TARGET_TABLE": eff["table"] or "",
            "TARGET_DATABASE": dest.target_database or "",
            "PRIMARY_KEY_COLUMNS": ",".join(dest.primary_key_columns or []),
            "STAGING_SCHEMA": dest.staging_schema or "",
            "STAGING_TABLE": eff["staging_table"] or "",
            "UPSERT_STRATEGY": dest.upsert_strategy or "",
            "TRUNCATE_BEFORE_LOAD": "true" if dest.truncate_before_load else "false",
        })
    return {k: v for k, v in env.items() if v != ""}
