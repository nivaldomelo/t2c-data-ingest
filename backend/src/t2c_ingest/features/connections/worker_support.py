"""Resolve registered connections for a job's Spark/Python execution.

A job references connections through its arguments as ``--<role>-connection <name|id>``
(e.g. ``--source-connection mysql_1 --target-connection postgres_1``). The worker resolves
each to a registered connection, validates it is active, decrypts the password, and exposes
the credentials to the job process as environment variables prefixed by the role:

    --source-connection  -> SOURCE_*   (SOURCE_HOST, SOURCE_PORT, SOURCE_DB, SOURCE_USER,
                                         SOURCE_PASSWORD, SOURCE_TYPE, SOURCE_SSL, SOURCE_SCHEMA)
    --target-connection  -> TARGET_*

Passwords travel ONLY via env vars, never via CLI args and never logged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from t2c_ingest.core.crypto import decrypt_secret
from t2c_ingest.features.connections.repository import get_connection_by_ref
from t2c_ingest.features.connections.service import test_connection


@dataclass
class ResolvedConnections:
    env: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)   # safe, no secrets
    error: str | None = None


def _prefix_for_flag(flag: str) -> str:
    # "--source-connection" -> "SOURCE_"
    role = flag.lstrip("-")
    if role.endswith("-connection"):
        role = role[: -len("-connection")]
    return role.replace("-", "_").upper() + "_"


def _extract_refs(arguments: list) -> dict[str, str]:
    """Return {prefix: ref} for every ``--<role>-connection <value>`` pair in the args."""
    refs: dict[str, str] = {}
    args = [str(a) for a in (arguments or [])]
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and a.endswith("-connection") and i + 1 < len(args):
            refs[_prefix_for_flag(a)] = args[i + 1]
            i += 2
        elif a.startswith("--") and "-connection=" in a:
            flag, _, value = a.partition("=")
            refs[_prefix_for_flag(flag)] = value
            i += 1
        else:
            i += 1
    return refs


def resolve_connections(db: Session, arguments: list, *, test: bool = True) -> ResolvedConnections:
    """Resolve, validate and (optionally) test the connections referenced by the arguments.

    Returns a ResolvedConnections with the env dict to inject. On any problem, ``error`` is set
    with a friendly message and the caller should fail the execution before submitting.
    """
    result = ResolvedConnections()
    refs = _extract_refs(arguments)
    if not refs:
        return result  # no connections referenced — nothing to inject

    for prefix, ref in refs.items():
        conn = get_connection_by_ref(db, ref)
        if conn is None:
            result.error = f"Conexão '{ref}' não encontrada (referenciada por {prefix[:-1].lower()})."
            return result
        if not conn.active:
            result.error = f"Conexão '{conn.name}' está inativa e não pode ser usada."
            return result

        password = decrypt_secret(conn.password_encrypted)
        result.env.update(
            {
                f"{prefix}TYPE": conn.connection_type or "",
                f"{prefix}HOST": conn.host or "",
                f"{prefix}PORT": str(conn.port or ""),
                f"{prefix}DB": conn.database_name or "",
                f"{prefix}USER": conn.username or "",
                f"{prefix}PASSWORD": password,
                f"{prefix}SSL": "true" if conn.ssl_enabled else "false",
                f"{prefix}SCHEMA": conn.schema_name or "",
            }
        )
        # Safe note (no secrets).
        result.notes.append(
            f"{prefix[:-1].lower()}-connection '{conn.name}' -> {conn.connection_type} "
            f"{conn.host}:{conn.port}/{conn.database_name} (ativa)"
        )

        if test:
            ok, message = test_connection(conn)
            result.notes.append(f"  teste {conn.name}: {'OK' if ok else 'FALHOU'} - {message}")
            if not ok:
                result.error = f"Teste de conectividade falhou para '{conn.name}': {message}"
                return result

    return result
