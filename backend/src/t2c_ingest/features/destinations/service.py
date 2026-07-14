"""Destinations service: validação declarativa e teste não-destrutivo por tipo (Postgres/S3)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.core.crypto import decrypt_secret
from t2c_ingest.features.connections import s3_service
from t2c_ingest.features.connections.service import _friendly_error, _resolve_ipv4
from t2c_ingest.models.connection import Connection
from t2c_ingest.models.destination import Destination


def get_connection(db: Session, connection_id: int) -> Connection | None:
    return db.get(Connection, connection_id)


def validate(data: dict, conn: Connection | None) -> None:
    """Valida a configuração declarativa do destino. Levanta ValueError com mensagem amigável."""
    dtype = data.get("destination_type")
    is_template = bool(data.get("is_template"))
    if conn is None:
        raise ValueError("Conexão do destino não encontrada.")
    if dtype == "postgres":
        if conn.connection_type != "postgres":
            raise ValueError("A conexão precisa ser do tipo PostgreSQL.")
        if not data.get("target_schema"):
            raise ValueError("Schema destino é obrigatório.")
        # Template: a tabela vem em runtime (Controle/arg); específico exige a tabela.
        if not is_template and not data.get("target_table"):
            raise ValueError("Tabela destino é obrigatória (ou marque como destino template).")
        if not data.get("write_mode"):
            raise ValueError("Modo de escrita é obrigatório.")
        if data.get("write_mode") == "upsert":
            if not data.get("primary_key_columns"):
                raise ValueError("Para upsert, informe as colunas chave.")
            # Template deriva a staging (stg_{table}) quando não informada.
            if not is_template and not data.get("staging_table"):
                raise ValueError("Para upsert, informe a tabela de staging.")
    elif dtype == "s3":
        if conn.connection_type != "s3":
            raise ValueError("A conexão precisa ser do tipo S3 / Data Lake.")
        if not data.get("target_bucket"):
            raise ValueError("Bucket é obrigatório.")
        if not data.get("target_layer"):
            raise ValueError("Camada é obrigatória.")
        # Template: prefixo/path é a RAIZ (a tabela é anexada em runtime) — pode ser vazio.
        if not is_template and not (data.get("target_prefix") or data.get("target_path")):
            raise ValueError("Prefixo ou path é obrigatório (ou marque como destino template).")
        if not data.get("file_format"):
            raise ValueError("Formato é obrigatório.")
        if not data.get("write_mode"):
            raise ValueError("Modo de escrita é obrigatório.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────── Teste ───────────────────────────────

def test_destination(db: Session, dest: Destination) -> dict:
    conn = get_connection(db, dest.connection_id)
    if not conn:
        return {"status": "failed", "message": "Conexão vinculada não encontrada.", "checks": []}
    if not conn.active:
        return {"status": "failed", "message": f"Conexão '{conn.name}' está inativa.", "checks": []}
    if dest.destination_type == "postgres":
        return _test_postgres_dest(dest, conn)
    if dest.destination_type == "s3":
        return _test_s3_dest(dest, conn)
    return {"status": "failed", "message": "Tipo de destino não suportado.", "checks": []}


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": ok, "detail": detail}


def _test_postgres_dest(dest: Destination, conn: Connection) -> dict:
    checks: list[dict] = []
    try:
        import psycopg
    except ImportError:  # pragma: no cover
        return {"status": "failed", "message": "Driver psycopg indisponível.", "checks": []}
    host = conn.host or "localhost"
    port = conn.port or 5432
    ipv4 = _resolve_ipv4(host, port)
    kw = dict(host=host, port=port, dbname=conn.database_name or "postgres", user=conn.username or "",
              password=decrypt_secret(conn.password_encrypted), connect_timeout=8,
              sslmode="require" if conn.ssl_enabled else "prefer")
    if ipv4:
        kw["hostaddr"] = ipv4
    try:
        with psycopg.connect(**kw) as pg:
            checks.append(_check("Conexão", True, f"{host}:{port}"))
            with pg.cursor() as cur:
                cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (dest.target_schema,))
                schema_ok = cur.fetchone() is not None
                checks.append(_check("Schema existe", schema_ok, dest.target_schema or ""))
                cur.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
                    (dest.target_schema, dest.target_table),
                )
                table_ok = cur.fetchone() is not None
                checks.append(_check("Tabela existe", table_ok, f"{dest.target_schema}.{dest.target_table}"
                                     if table_ok else "será criada na carga, se o job permitir"))
                if table_ok:
                    cur.execute("SELECT has_table_privilege(%s, 'INSERT')",
                                (f"{dest.target_schema}.{dest.target_table}",))
                    write_ok = bool(cur.fetchone()[0])
                    checks.append(_check("Permissão de escrita (INSERT)", write_ok))
                if dest.write_mode == "upsert" and dest.staging_table:
                    st_schema = dest.staging_schema or dest.target_schema
                    cur.execute(
                        "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
                        (st_schema, dest.staging_table),
                    )
                    checks.append(_check("Staging table existe", cur.fetchone() is not None,
                                         f"{st_schema}.{dest.staging_table}"))
        # Sucesso geral se conexão + schema OK (tabela pode ser criada na carga).
        required_ok = all(c["ok"] for c in checks if c["name"] in ("Conexão", "Schema existe"))
        return {
            "status": "success" if required_ok else "failed",
            "message": "Destino PostgreSQL validado." if required_ok else "Validação encontrou problemas — veja os detalhes.",
            "checks": checks,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "message": _friendly_error(str(exc)), "checks": checks}


def _test_s3_dest(dest: Destination, conn: Connection) -> dict:
    checks: list[dict] = []
    try:
        from t2c_ingest.features.destinations.resolver import _clean_prefix
        client = s3_service.build_client(conn)
        bucket = dest.target_bucket
        prefix = s3_service.sanitize_prefix(_clean_prefix(dest.target_prefix))
        # Bucket acessível (ListObjects com o prefixo do destino, MaxKeys=1).
        client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
        checks.append(_check("Bucket acessível", True, bucket or ""))
        checks.append(_check("Prefixo/path", True, prefix or "(raiz)"))
        checks.append(_check("Formato", True, dest.file_format or "parquet"))
        # Escrita não-destrutiva: grava e remove um objeto temporário no prefixo do destino.
        can_write = conn.can_write
        if can_write:
            key = f"{prefix.rstrip('/') + '/' if prefix else ''}_t2c_destination_tests/test.txt"
            try:
                client.put_object(Bucket=bucket, Key=key, Body=b"t2c destination test")
                checks.append(_check("Permissão de escrita", True))
                try:
                    client.delete_object(Bucket=bucket, Key=key)
                except Exception:  # noqa: BLE001
                    pass
            except Exception as exc:  # noqa: BLE001
                checks.append(_check("Permissão de escrita", False, type(exc).__name__))
        else:
            checks.append(_check("Permissão de escrita", False, "conexão sem escrita habilitada"))
        ok = all(c["ok"] for c in checks if c["name"] in ("Bucket acessível", "Prefixo/path"))
        return {"status": "success" if ok else "failed",
                "message": "Destino S3 validado." if ok else "Validação encontrou problemas.",
                "checks": checks}
    except ValueError as exc:
        return {"status": "failed", "message": str(exc), "checks": checks}
    except Exception as exc:  # noqa: BLE001
        code = (exc.response.get("Error", {}).get("Code") if hasattr(exc, "response") else None) or type(exc).__name__
        return {"status": "failed", "message": f"Não foi possível acessar o destino S3: {code}", "checks": checks}


def name_in_use(db: Session, name: str, exclude_id: int | None = None) -> bool:
    stmt = select(Destination.id).where(Destination.name == name, Destination.deleted_at.is_(None))
    if exclude_id:
        stmt = stmt.where(Destination.id != exclude_id)
    return db.scalar(stmt) is not None
