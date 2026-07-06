"""T2C Data Ingest execution worker (Phase 2 skeleton).

Polls the ``executions`` table for ``queued`` rows and runs them OUTSIDE the API process:
  - python / spark_python via ``spark-submit`` to the Spark master, or plain ``python`` for
    pure-Python jobs.
  - Captures stdout/stderr into ``execution_logs`` and updates status/duration.

This is intentionally simple and single-process. It is the seam where a real queue
(Celery/Redis/K8s Jobs) plugs in later; the API contract (queued -> running -> success/failed)
does not change.
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select, update  # noqa: E402

from t2c_ingest.core.config import settings  # noqa: E402
from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.models.execution import Execution, ExecutionLog  # noqa: E402
from t2c_ingest.models.job import JobDefinition  # noqa: E402


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(db, execution_id: int, seq: int, level: str, message: str) -> int:
    db.add(
        ExecutionLog(
            execution_id=execution_id,
            seq=seq,
            level=level,
            message=message[:100_000],
            logged_at=_now(),
        )
    )
    db.commit()
    return seq + 1


def _claim_next(db) -> Execution | None:
    """Atomically claim one queued execution (SKIP LOCKED avoids two workers racing)."""
    execution = db.scalar(
        select(Execution)
        .where(Execution.status == "queued", Execution.target_type == "job")
        .order_by(Execution.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if execution is None:
        return None
    execution.status = "running"
    execution.started_at = _now()
    db.commit()
    return execution


def _build_command(job: JobDefinition, execution: Execution) -> list[str]:
    args = [str(a) for a in (job.arguments or [])]
    if job.type in {"spark_python", "spark_submit"}:
        cmd = ["spark-submit", "--master", settings.spark_master_url]
        if job.type == "spark_submit" and job.main_class:
            cmd += ["--class", job.main_class]
        cmd += [job.script_path or ""]
        return cmd + args
    # plain python
    return ["python", job.script_path or ""] + args


def _run_one(db, execution: Execution) -> None:
    seq = 0
    job = db.get(JobDefinition, execution.job_id) if execution.job_id else None
    if not job or not job.script_path:
        execution.status = "failed"
        execution.finished_at = _now()
        execution.final_message = "Job or script_path missing"
        db.commit()
        return

    cmd = _build_command(job, execution)
    seq = _log(db, execution.id, seq, "INFO", f"$ {' '.join(cmd)}")
    started = time.monotonic()
    try:
        env = {**(job.env_vars or {})}
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=job.timeout_seconds or None,
            env={**_os_environ(), **{k: str(v) for k, v in env.items()}},
        )
        if proc.stdout:
            seq = _log(db, execution.id, seq, "INFO", proc.stdout)
        if proc.stderr:
            seq = _log(db, execution.id, seq, "ERROR" if proc.returncode else "WARNING", proc.stderr)
        duration = int(time.monotonic() - started)
        if proc.returncode == 0:
            execution.status = "success"
            execution.final_message = "Completed successfully"
        else:
            execution.status = "failed"
            execution.final_message = f"Exited with code {proc.returncode}"
        execution.duration_seconds = duration
    except subprocess.TimeoutExpired:
        execution.status = "timeout"
        execution.final_message = f"Timed out after {job.timeout_seconds}s"
        execution.duration_seconds = int(time.monotonic() - started)
        _log(db, execution.id, seq, "ERROR", "Execution timed out")
    except Exception as exc:  # noqa: BLE001
        execution.status = "failed"
        execution.final_message = str(exc)
        execution.error_trace = repr(exc)
        execution.duration_seconds = int(time.monotonic() - started)
        _log(db, execution.id, seq, "ERROR", repr(exc))
    finally:
        execution.finished_at = _now()
        db.commit()


def _os_environ() -> dict:
    import os

    return dict(os.environ)


def main() -> None:
    poll = settings.worker_poll_interval_seconds
    print(f"[worker] started; polling every {poll}s; spark master={settings.spark_master_url}")
    while True:
        with SessionLocal() as db:
            execution = _claim_next(db)
            if execution is None:
                time.sleep(poll)
                continue
            print(f"[worker] running execution {execution.id} ({execution.target_name})")
            _run_one(db, execution)
            print(f"[worker] execution {execution.id} -> {execution.status}")


if __name__ == "__main__":
    main()
