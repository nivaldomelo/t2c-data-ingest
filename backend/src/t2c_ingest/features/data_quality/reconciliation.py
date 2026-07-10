"""Real reconciliation checks — query the actual source & target databases.

Beyond the INGEST_SUMMARY-derived checks, this opens *bounded, read-only* queries against the
registered source and target connections to validate, per ingested table:

  - reconcile_count : COUNT(*) on source vs target (they should converge)
  - pk_not_null     : no NULLs in the primary-key column(s) on the target
  - pk_duplicates   : no duplicate primary keys on the target

Defensive by construction: identifiers are validated against a strict allow-list before being
interpolated, statements are read-only with a short timeout, and any failure becomes a "skip"
check instead of an exception — it must never break the execution. Credentials are decrypted
only in-process (via the same Fernet path as the worker) and are never logged.
"""
from __future__ import annotations

import re

from t2c_ingest.core.config import settings
from t2c_ingest.core.crypto import decrypt_secret
from t2c_ingest.models.connection import Connection

# Identifier parts must be plain SQL identifiers (no quotes/spaces/semicolons). Anything else is
# rejected and the check is skipped — we never interpolate untrusted text into SQL.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _split_ident(name: str | None) -> list[str] | None:
    """Split ``schema.table`` (or ``table``) into validated parts, or None if any part is invalid."""
    parts = [p.strip() for p in str(name or "").split(".") if p.strip()]
    if not parts or len(parts) > 2 or not all(_IDENT_RE.match(p) for p in parts):
        return None
    return parts


def _quote(parts: list[str], kind: str) -> str:
    q = '"' if kind == "postgres" else "`"
    return ".".join(f"{q}{p}{q}" for p in parts)


def _scalar(conn: Connection, sql: str) -> int | None:
    """Run a single read-only scalar query against ``conn`` with a bounded timeout."""
    timeout = max(1, int(settings.dq_reconcile_timeout or 8))
    ctype = (conn.connection_type or "").lower()
    password = decrypt_secret(conn.password_encrypted) if conn.password_encrypted else ""
    if ctype == "postgres":
        import psycopg

        with psycopg.connect(
            host=conn.host or "localhost", port=int(conn.port or 5432),
            dbname=conn.database_name or "", user=conn.username or "", password=password,
            connect_timeout=timeout, autocommit=True,
        ) as c:
            with c.cursor() as cur:
                cur.execute(f"SET statement_timeout = {timeout * 1000}")
                cur.execute(sql)
                row = cur.fetchone()
                return int(row[0]) if row and row[0] is not None else None
    if ctype == "mysql":
        import pymysql

        c = pymysql.connect(
            host=conn.host or "localhost", port=int(conn.port or 3306),
            user=conn.username or "", password=password, database=conn.database_name or None,
            connect_timeout=timeout, read_timeout=timeout, write_timeout=timeout,
        )
        try:
            with c.cursor() as cur:
                cur.execute(f"SET SESSION MAX_EXECUTION_TIME={timeout * 1000}")
                cur.execute(sql)
                row = cur.fetchone()
                return int(row[0]) if row and row[0] is not None else None
        finally:
            c.close()
    raise RuntimeError(f"tipo de conexão não suportado: {conn.connection_type}")


def _skip(name: str, exc: Exception) -> dict:
    # Keep the reason but never surface credentials/DSNs.
    reason = str(exc).splitlines()[0][:160] if str(exc) else exc.__class__.__name__
    return {"name": name, "status": "skip", "detail": f"não verificado: {reason}"}


def run(
    source_conn: Connection | None, source_table: str | None,
    target_conn: Connection | None, target_table: str | None,
    pk_columns: list[str] | None, tipo: str | None,
) -> list[dict]:
    """Return reconciliation check dicts (same shape as _evaluate_checks). Never raises."""
    checks: list[dict] = []
    tipo = (tipo or "").upper()

    # ── reconcile_count: source vs target ──
    if source_conn is not None and target_conn is not None:
        s_parts = _split_ident(source_table)
        t_parts = _split_ident(target_table)
        if not s_parts or not t_parts:
            checks.append({"name": "reconcile_count", "status": "skip",
                           "detail": "tabela origem/destino não identificada"})
        else:
            try:
                s_type = (source_conn.connection_type or "").lower()
                t_type = (target_conn.connection_type or "").lower()
                src = _scalar(source_conn, f"SELECT COUNT(*) FROM {_quote(s_parts, s_type)}")
                tgt = _scalar(target_conn, f"SELECT COUNT(*) FROM {_quote(t_parts, t_type)}")
                detail = f"origem={src} destino={tgt}"
                if src == tgt:
                    status = "pass"
                elif tipo == "FULL":
                    status = "fail"
                    detail += " (FULL: contagens deveriam ser iguais)"
                else:
                    status = "warn"
                    detail += f" ({tipo or 'INCREMENTAL'}: contagens divergem)"
                checks.append({"name": "reconcile_count", "status": status, "detail": detail})
            except Exception as exc:  # noqa: BLE001
                checks.append(_skip("reconcile_count", exc))

    # ── primary-key checks on the target ──
    pk = [c.strip() for c in (pk_columns or []) if c and _IDENT_RE.match(c.strip())]
    if target_conn is not None and pk:
        t_parts = _split_ident(target_table)
        if not t_parts:
            checks.append({"name": "pk_not_null", "status": "skip", "detail": "tabela destino não identificada"})
            checks.append({"name": "pk_duplicates", "status": "skip", "detail": "tabela destino não identificada"})
        else:
            t_type = (target_conn.connection_type or "").lower()
            q = '"' if t_type == "postgres" else "`"
            tbl = _quote(t_parts, t_type)
            cols = [f"{q}{c}{q}" for c in pk]
            # pk_not_null
            try:
                where_null = " OR ".join(f"{c} IS NULL" for c in cols)
                nulls = _scalar(target_conn, f"SELECT COUNT(*) FROM {tbl} WHERE {where_null}")
                checks.append({"name": "pk_not_null",
                               "status": "pass" if (nulls or 0) == 0 else "fail",
                               "detail": f"PK({','.join(pk)}) nulos={nulls}"})
            except Exception as exc:  # noqa: BLE001
                checks.append(_skip("pk_not_null", exc))
            # pk_duplicates
            try:
                group_by = ", ".join(cols)
                dups = _scalar(
                    target_conn,
                    f"SELECT COUNT(*) FROM (SELECT 1 FROM {tbl} GROUP BY {group_by} HAVING COUNT(*) > 1) t",
                )
                checks.append({"name": "pk_duplicates",
                               "status": "pass" if (dups or 0) == 0 else "fail",
                               "detail": f"PK({','.join(pk)}) chaves duplicadas={dups}"})
            except Exception as exc:  # noqa: BLE001
                checks.append(_skip("pk_duplicates", exc))

    return checks
