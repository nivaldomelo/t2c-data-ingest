"""Read-only SQL guard for the Data Lake quick-query.

Enforces the security rules from the spec: only read commands (SELECT/WITH/SHOW/DESCRIBE/
EXPLAIN), block every destructive/DDL/session command, block multiple statements, and force a
LIMIT. This is a defensive allowlist — anything not clearly a read is rejected.
"""
from __future__ import annotations

import re

# Commands explicitly allowed to START a query.
_ALLOWED_HEADS = ("select", "with", "show", "describe", "desc", "explain")

# Tokens that must never appear (word-boundary) anywhere in the statement. Covers DML/DDL and
# session/catalog mutations even when nested (e.g. a CTE hiding an INSERT, `SET`, `ADD JAR`).
_BLOCKED = (
    "insert", "update", "delete", "merge", "drop", "alter", "create", "truncate",
    "call", "set", "add", "cache", "uncache", "refresh", "msck", "load", "grant",
    "revoke", "analyze", "export", "import", "replace", "overwrite", "reset",
)
_BLOCKED_RE = re.compile(r"(?is)\b(" + "|".join(_BLOCKED) + r")\b")

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


class SqlGuardError(ValueError):
    """Raised when a query violates the read-only policy."""


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)  # /* block */
    sql = re.sub(r"--[^\n]*", " ", sql)                     # -- line
    return sql


def _split_statements(sql: str) -> list[str]:
    """Split on ';' that is not inside a quoted string. Trailing empty parts are dropped."""
    parts, buf, quote = [], [], None
    for ch in sql:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"', "`"):
            quote = ch
            buf.append(ch)
        elif ch == ";":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def validate_read_only(sql: str) -> str:
    """Validate a single read-only statement. Returns the cleaned SQL or raises SqlGuardError."""
    if not sql or not sql.strip():
        raise SqlGuardError("Consulta vazia.")
    clean = _strip_comments(sql).strip()
    statements = _split_statements(clean)
    if len(statements) == 0:
        raise SqlGuardError("Consulta vazia.")
    if len(statements) > 1:
        raise SqlGuardError("Apenas uma consulta por vez é permitida (não use ';' para múltiplos comandos).")
    stmt = statements[0]
    head = stmt.split(None, 1)[0].lower() if stmt.split() else ""
    if head not in _ALLOWED_HEADS:
        raise SqlGuardError(
            f"Comando '{head or '?'}' não permitido. Use apenas SELECT, WITH, SHOW, DESCRIBE ou EXPLAIN."
        )
    blocked = _BLOCKED_RE.search(stmt)
    if blocked:
        raise SqlGuardError(f"Comando não permitido na consulta rápida: '{blocked.group(1).upper()}'.")
    return stmt


_LIMIT_RE = re.compile(r"(?is)\blimit\s+\d+\s*$")


def apply_limit(stmt: str, limit: int | None) -> tuple[str, int]:
    """Ensure the statement has a bounded LIMIT. Returns (sql, effective_limit).

    Only SELECT/WITH get a LIMIT appended; SHOW/DESCRIBE/EXPLAIN are naturally small and left
    as-is. If the user already wrote a LIMIT it is capped to MAX_LIMIT.
    """
    eff = DEFAULT_LIMIT if not limit or limit <= 0 else min(int(limit), MAX_LIMIT)
    head = stmt.split(None, 1)[0].lower()
    if head not in ("select", "with"):
        return stmt, eff
    existing = _LIMIT_RE.search(stmt)
    if existing:
        # Cap an existing trailing LIMIT to MAX_LIMIT.
        current = int(re.search(r"\d+", existing.group(0)).group(0))
        capped = min(current, MAX_LIMIT)
        return _LIMIT_RE.sub(f"LIMIT {capped}", stmt), capped
    return f"{stmt.rstrip().rstrip(';')} LIMIT {eff}", eff


# Logical name "bronze.clientes" -> safe temp view "bronze__clientes".
_LOGICAL_NAME_RE = re.compile(r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b")


def translate_logical_names(stmt: str, known: set[str]) -> str:
    """Rewrite ``schema.table`` references to the ``schema__table`` temp-view names the Spark
    job registers. Only rewrites pairs whose ``schema__table`` is in ``known`` to avoid touching
    unrelated dotted identifiers (e.g. function calls)."""
    def repl(m: re.Match) -> str:
        candidate = f"{m.group(1)}__{m.group(2)}"
        return candidate if candidate in known else m.group(0)

    return _LOGICAL_NAME_RE.sub(repl, stmt)
