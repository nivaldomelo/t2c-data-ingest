"""Unit tests for orchestration/logic helpers (no DB/network)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from t2c_ingest.features.pipelines import runner
from t2c_ingest.features.variables.service import _env_key
from t2c_ingest.features.alerts import service as alerts
from t2c_ingest.features.executions.log_parser import parse_ingest_summary, parse_connections
from t2c_ingest.features.schedules.service import compute_next_run


def _up(status):
    return SimpleNamespace(status=status)


def test_dependency_types():
    assert runner._dep_satisfied("success", _up("success")) is True
    assert runner._dep_satisfied("success", _up("failed")) is False
    assert runner._dep_impossible("success", _up("failed")) is True
    assert runner._dep_satisfied("failed", _up("failed")) is True
    assert runner._dep_satisfied("always", _up("failed")) is True
    assert runner._dep_satisfied("finished", _up("skipped")) is True
    # still running -> neither satisfied nor impossible (wait)
    assert runner._dep_satisfied("success", _up("running")) is False
    assert runner._dep_impossible("success", _up("running")) is False
    # missing upstream -> impossible
    assert runner._dep_impossible("success", None) is True


def test_env_key():
    assert _env_key("warehouse-url") == "WAREHOUSE_URL"
    assert _env_key("api.key") == "API_KEY"
    assert _env_key("2bad") is None
    assert _env_key("") is None


def test_alert_retry_backoff():
    now = datetime.now(timezone.utc)
    due = SimpleNamespace(status="failed", attempts=1, sent_at=now - timedelta(seconds=10_000))
    not_due = SimpleNamespace(status="failed", attempts=1, sent_at=now)
    exhausted = SimpleNamespace(status="failed", attempts=999, sent_at=None)
    assert alerts._retry_due(due, now) is True
    assert alerts._retry_due(not_due, now) is False
    assert alerts._retry_due(exhausted, now) is False


def test_parse_ingest_summary():
    line = "INGEST_SUMMARY: table=massa_teste.clientes tipo=FULL lidos=1000 gravados=1000 status=SUCESSO"
    s = parse_ingest_summary(line)
    assert s and s["table"] == "massa_teste.clientes" and s["tipo"] == "FULL"
    assert parse_ingest_summary("linha sem summary") is None


def test_compute_next_run_no_catchup():
    tz = "America/Sao_Paulo"
    # hourly cron; asking from a point in time returns a STRICTLY future slot (no backfill).
    after = datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc)
    nxt = compute_next_run("0 * * * *", tz, after=after)
    assert nxt > after
    # next run of an hourly schedule is within the next hour, never a missed past slot
    assert nxt <= after + timedelta(hours=1, minutes=5)
