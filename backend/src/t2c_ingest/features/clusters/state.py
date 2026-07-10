"""Live cluster state from the Spark master REST (`/json/`).

The Spark standalone master exposes a JSON status with alive workers, total cores and memory.
We read it directly (the API/worker are on the same Docker network) so the Clusters screen shows
real, current data instead of stale DB counters.
"""
from __future__ import annotations

import json
import re
import socket
import urllib.request
from datetime import datetime, timezone

from t2c_ingest.core.config import settings


def _fmt_memory(mb: int | None) -> str | None:
    if not mb:
        return None
    if mb % 1024 == 0:
        return f"{mb // 1024}G"
    return f"{round(mb / 1024, 1)}G"


def _resolve_name(host: str, index: int) -> str:
    """Best-effort friendly worker name (reverse DNS on the docker network), else a label."""
    try:
        socket.setdefaulttimeout(1.5)
        full = socket.gethostbyaddr(host)[0]
        m = re.search(r"spark-worker-\d+", full)  # prefer the friendly compose service name
        if m:
            return m.group(0)
        name = full.split(".")[0]
        if name:
            return name
    except Exception:  # noqa: BLE001
        pass
    finally:
        socket.setdefaulttimeout(None)
    return f"worker-{index}"


def _fetch_master_state_uncached() -> dict | None:
    url = settings.runtime_spark_master_webui.rstrip("/") + "/json/"
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            return json.loads(resp.read().decode())
    except Exception:  # noqa: BLE001
        return None


def fetch_master_state() -> dict | None:
    """Return the raw master JSON (cached briefly so many pollers share one HTTP call)."""
    from t2c_ingest.core.cache import cached

    return cached("spark:master-state", 5.0, _fetch_master_state_uncached)


def summarize(state: dict | None) -> dict:
    """Derive worker count / cores / memory / status from a master state payload."""
    if not state:
        return {"workers": 0, "cores": 0, "memory": None, "reachable": False}
    alive = [w for w in state.get("workers", []) if w.get("state") == "ALIVE"]
    cores = sum(w.get("cores", 0) for w in alive)
    memory_mb = sum(w.get("memory", 0) for w in alive)
    return {
        "workers": len(alive),
        "cores": cores,
        "memory": _fmt_memory(memory_mb),
        "reachable": True,
    }


def list_workers(state: dict | None) -> list[dict]:
    """Return per-worker info (friendly name, status, cores, memory, host, heartbeat)."""
    if not state:
        return []
    out = []
    for i, w in enumerate(state.get("workers", []), start=1):
        host = w.get("host") or ""
        st = w.get("state", "")
        status = {"ALIVE": "active", "DEAD": "error"}.get(st, "inactive")
        hb = w.get("lastheartbeat")
        hb_dt = datetime.fromtimestamp(hb / 1000, tz=timezone.utc) if hb else None
        out.append({
            "name": _resolve_name(host, i),
            "status": status,
            "host": host,
            "cores": w.get("cores"),
            "memory": _fmt_memory(w.get("memory")),
            "last_heartbeat_at": hb_dt,
        })
    return out
