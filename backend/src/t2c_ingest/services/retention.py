"""Retention: prune old rows from append-only tables in bounded batches.

Runs periodically in the worker. Each table has its own configurable window (days); 0 disables
that table. Deletes in batches so a big backlog never locks the table in one giant transaction.
Best-effort — never raises into the worker loop.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings

_BATCH = 5000

# (table, timestamp column, retention-days setting attr). execution_logs cascades from executions,
# but we also prune it directly by age so logs of still-referenced runs are bounded.
_TABLES = [
    ("execution_logs", "created_at", "retention_execution_logs_days"),
    ("schedule_runs", "created_at", "retention_schedule_runs_days"),
    ("alert_notifications", "created_at", "retention_alert_notifications_days"),
    ("audit_events", "created_at", "retention_audit_days"),
    # executions last: only terminal runs, and their logs cascade.
    ("executions", "created_at", "retention_executions_days"),
]


def _prune(db: Session, table: str, ts_col: str, days: int) -> int:
    schema = settings.db_schema or "t2c_data_ingest"
    where_terminal = ""
    if table == "executions":
        # never delete rows that are still queued/running.
        where_terminal = " AND status NOT IN ('queued','running')"
    total = 0
    while True:
        result = db.execute(text(f"""
            DELETE FROM "{schema}".{table}
            WHERE id IN (
                SELECT id FROM "{schema}".{table}
                WHERE {ts_col} < (now() - make_interval(days => :days)){where_terminal}
                LIMIT :batch
            )
        """), {"days": days, "batch": _BATCH})
        db.commit()
        deleted = result.rowcount or 0
        total += deleted
        if deleted < _BATCH:
            break
    return total


def run_retention(db: Session) -> dict[str, int]:
    """Prune every configured table. Returns {table: rows_deleted}. Never raises."""
    summary: dict[str, int] = {}
    for table, ts_col, attr in _TABLES:
        days = int(getattr(settings, attr, 0) or 0)
        if days <= 0:
            continue
        try:
            n = _prune(db, table, ts_col, days)
            if n:
                summary[table] = n
        except Exception as exc:  # noqa: BLE001 - retention must never break the worker
            db.rollback()
            print(f"[retention] {table} skipped: {exc}")
    return summary
