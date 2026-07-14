"""IngestionSourceResolver / IngestionTargetResolver (CTRL-1).

Resolvem origem e destino de uma carga a partir do Controle de Ingestão, de forma DECLARATIVA e
SEM segredos (só metadados; credenciais ficam na conexão e são injetadas pelo worker). O destino
prioriza destination_id (entidade Destinos); senão usa os campos target_* do próprio controle.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from t2c_ingest.features.destinations import resolver as dest_resolver
from t2c_ingest.models.connection import Connection
from t2c_ingest.models.destination import Destination


def _split_table(nome: str | None) -> tuple[str | None, str | None]:
    if not nome:
        return None, None
    if "." in nome:
        s, t = nome.split(".", 1)
        return s, t
    return None, nome


def _conn(db: Session, cid: int | None) -> Connection | None:
    return db.get(Connection, cid) if cid else None


def resolve_source(db: Session, control) -> dict:
    conn = _conn(db, control.source_connection_id)
    schema_guess, table_guess = _split_table(control.nome_tabela)
    is_incr = (control.tipo_ingestao or "").upper() == "INCREMENTAL"
    return {
        "source_type": (conn.connection_type if conn else (control.origem or "").lower() or None),
        "connection_id": control.source_connection_id,
        "connection_name": conn.name if conn else None,
        "database": control.source_database or (conn.database_name if conn else None),
        "schema": control.source_schema or schema_guess,
        "table": control.source_table or table_guess,
        "query": control.source_query,
        "path": control.source_path,
        "file_format": control.source_file_format,
        "incremental_column": (control.coluna_ultima_alteracao or control.coluna_data) if is_incr else None,
        "watermark": control.watermark_atual.isoformat() if control.watermark_atual else None,
    }


def _runtime_table(control) -> str | None:
    if control.target_table:
        return control.target_table
    _, t = _split_table(control.nome_tabela)
    return control.source_table or t


def resolve_target(db: Session, control) -> dict:
    # 1) destino configurável (entidade Destinos) tem prioridade.
    if control.destination_id:
        dest = db.get(Destination, control.destination_id)
        if dest and dest.deleted_at is None:
            conn = _conn(db, dest.connection_id)
            norm = dest_resolver.normalized(dest, conn, _runtime_table(control) if dest.is_template else None)
            t = norm["target"]
            return {
                "target_type": dest.destination_type, "connection_id": dest.connection_id,
                "connection_name": conn.name if conn else None, "destination_id": dest.id,
                "via_destination": True, **t,
            }
    # 2) campos target_* do próprio controle.
    conn = _conn(db, control.target_connection_id)
    ttype = (conn.connection_type if conn else None) or ("s3" if control.target_bucket else "postgres")
    base = {
        "target_type": ttype, "connection_id": control.target_connection_id,
        "connection_name": conn.name if conn else None, "destination_id": None, "via_destination": False,
        "write_mode": control.write_mode or ("append" if ttype == "s3" else "append"),
    }
    if ttype == "s3":
        prefix = (control.target_prefix or "").strip("/")
        path = control.target_path or (f"s3a://{control.target_bucket}/{prefix}/" if control.target_bucket else None)
        base.update({
            "bucket": control.target_bucket, "prefix": prefix or None, "path": path,
            "layer": control.target_layer, "file_format": control.file_format,
            "compression": control.compression, "partition_columns": control.partition_columns or [],
        })
    else:
        base.update({
            "schema": control.target_schema, "table": control.target_table or _runtime_table(control),
            "database": control.target_database,
            "primary_key_columns": [c.strip() for c in (control.colunas_chave or "").split(",") if c.strip()],
            "staging_schema": control.staging_schema, "staging_table": control.staging_table,
            "upsert_strategy": control.upsert_strategy, "truncate_before_load": control.truncate_before_load,
        })
    return base


def source_env(src: dict) -> dict[str, str]:
    """Env NÃO-secreto da origem (credenciais são injetadas à parte pelo worker)."""
    env = {"SOURCE_TYPE": src.get("source_type") or ""}
    for key, col in (("SOURCE_SCHEMA", "schema"), ("SOURCE_TABLE", "table"), ("SOURCE_QUERY", "query"),
                     ("SOURCE_PATH", "path"), ("SOURCE_FILE_FORMAT", "file_format"),
                     ("SOURCE_INCREMENTAL_COLUMN", "incremental_column"), ("SOURCE_WATERMARK", "watermark")):
        v = src.get(col)
        if v:
            env[key] = str(v)
    return env


def target_env(tgt: dict) -> dict[str, str]:
    """Env NÃO-secreto do destino resolvido pelo controle."""
    env = {"TARGET_TYPE": tgt.get("target_type") or "", "WRITE_MODE": tgt.get("write_mode") or "append"}
    if tgt.get("target_type") == "s3":
        mapping = {"TARGET_BUCKET": "bucket", "TARGET_PREFIX": "prefix", "TARGET_PATH": "path",
                   "TARGET_LAYER": "layer", "FILE_FORMAT": "file_format", "COMPRESSION": "compression"}
        for k, c in mapping.items():
            if tgt.get(c):
                env[k] = str(tgt[c])
        if tgt.get("partition_columns"):
            env["PARTITION_COLUMNS"] = ",".join(tgt["partition_columns"])
    else:
        mapping = {"TARGET_SCHEMA": "schema", "TARGET_TABLE": "table", "TARGET_DATABASE": "database",
                   "STAGING_SCHEMA": "staging_schema", "STAGING_TABLE": "staging_table",
                   "UPSERT_STRATEGY": "upsert_strategy"}
        for k, c in mapping.items():
            if tgt.get(c):
                env[k] = str(tgt[c])
        if tgt.get("primary_key_columns"):
            env["PRIMARY_KEY_COLUMNS"] = ",".join(tgt["primary_key_columns"])
        if tgt.get("truncate_before_load"):
            env["TRUNCATE_BEFORE_LOAD"] = "true"
    return env
