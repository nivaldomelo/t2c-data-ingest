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

import glob
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from t2c_ingest.core.config import settings  # noqa: E402
from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.features.connections.worker_support import resolve_connections  # noqa: E402
from t2c_ingest.models.execution import Execution, ExecutionArtifact, ExecutionLog  # noqa: E402
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


def _jdbc_jar_args() -> list[str]:
    """Prefer local JDBC jars (mounted from ./spark/jars); otherwise fetch via --packages."""
    jars = sorted(glob.glob(os.path.join(settings.spark_local_jars_dir, "*.jar")))
    if jars:
        return ["--jars", ",".join(jars)]
    if settings.spark_jdbc_packages.strip():
        return ["--packages", settings.spark_jdbc_packages.strip()]
    return []


def _build_command(job: JobDefinition) -> list[str]:
    args = [str(a) for a in (job.arguments or [])]
    if job.type in {"spark_python", "spark_submit"}:
        cmd = ["spark-submit", "--master", settings.spark_master_url]
        # Driver host/bind for standalone client mode. Spark rejects hostnames with '_'
        # ("Invalid Spark URL"), so we advertise a DNS-valid name (the compose service).
        if settings.spark_driver_host:
            cmd += ["--conf", f"spark.driver.host={settings.spark_driver_host}"]
        if settings.spark_driver_bind_address:
            cmd += ["--conf", f"spark.driver.bindAddress={settings.spark_driver_bind_address}"]
        cmd += _jdbc_jar_args()
        # Prefer IPv4 in the JVM (Docker bridge often lacks an IPv6 route).
        cmd += [
            "--conf",
            "spark.driver.extraJavaOptions=-Djava.net.preferIPv4Stack=true",
            "--conf",
            "spark.executor.extraJavaOptions=-Djava.net.preferIPv4Stack=true",
        ]
        if job.type == "spark_submit" and job.main_class:
            cmd += ["--class", job.main_class]
        cmd += [job.script_path or ""]
        return cmd + args
    # plain python
    return ["python", job.script_path or ""] + args


def _redact(cmd: list[str]) -> str:
    """Command line for logging. Connection args carry only names, and passwords are never
    on the command line (they go via env), so the command is safe to log verbatim."""
    return " ".join(cmd)


def _capture_summary(db, execution: Execution, stdout: str) -> None:
    for line in stdout.splitlines():
        if line.startswith("INGEST_SUMMARY:"):
            summary = line[len("INGEST_SUMMARY:"):].strip()
            execution.final_message = summary
            db.add(
                ExecutionArtifact(
                    execution_id=execution.id, name="ingest_summary", kind="metric", uri=summary
                )
            )
            return


def _run_one(db, execution: Execution) -> None:
    seq = 0
    job = db.get(JobDefinition, execution.job_id) if execution.job_id else None
    if not job or not job.script_path:
        execution.status = "failed"
        execution.finished_at = _now()
        execution.final_message = "Job or script_path missing"
        db.commit()
        return

    # Resolve registered connections referenced in the job args (validates active + tests).
    connection_env: dict[str, str] = {}
    try:
        resolved = resolve_connections(db, job.arguments or [], test=True)
        for note in resolved.notes:
            seq = _log(db, execution.id, seq, "INFO", note)
        if resolved.error:
            execution.status = "failed"
            execution.final_message = resolved.error
            execution.finished_at = _now()
            _log(db, execution.id, seq, "ERROR", resolved.error)
            db.commit()
            return
        connection_env = resolved.env
    except Exception as exc:  # noqa: BLE001
        execution.status = "failed"
        execution.final_message = f"Falha ao resolver conexões: {exc}"
        execution.error_trace = repr(exc)
        execution.finished_at = _now()
        _log(db, execution.id, seq, "ERROR", repr(exc))
        db.commit()
        return

    cmd = _build_command(job)
    seq = _log(db, execution.id, seq, "INFO", f"$ {_redact(cmd)}")
    started = time.monotonic()
    try:
        # Env precedence: process env <- job.env_vars <- resolved connection creds.
        env = {**_os_environ()}
        env.update({k: str(v) for k, v in (job.env_vars or {}).items()})
        env.update(connection_env)  # SOURCE_*/TARGET_* (includes decrypted passwords)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=job.timeout_seconds or None,
            env=env,
        )
        if proc.stdout:
            seq = _log(db, execution.id, seq, "INFO", proc.stdout)
        if proc.stderr:
            seq = _log(db, execution.id, seq, "ERROR" if proc.returncode else "WARNING", proc.stderr)
        duration = int(time.monotonic() - started)
        if proc.returncode == 0:
            execution.status = "success"
            execution.final_message = "Completed successfully"
            _capture_summary(db, execution, proc.stdout or "")
        else:
            execution.status = "failed"
            execution.final_message = f"Exited with code {proc.returncode}"
            execution.error_trace = (proc.stderr or "")[:20000]
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
    return dict(os.environ)


def _advance_pipelines() -> None:
    """Progress running pipeline executions (release ready steps, finalize)."""
    try:
        from t2c_ingest.features.pipelines.runner import advance_pipeline_executions

        with SessionLocal() as db:
            advance_pipeline_executions(db)
    except Exception as exc:  # noqa: BLE001 - never let orchestration kill the worker loop
        print(f"[worker] pipeline advance error: {exc}")


def main() -> None:
    poll = settings.worker_poll_interval_seconds
    print(f"[worker] started; polling every {poll}s; spark master={settings.spark_master_url}")
    while True:
        ran = False
        with SessionLocal() as db:
            execution = _claim_next(db)
            if execution is not None:
                ran = True
                print(f"[worker] running execution {execution.id} ({execution.target_name})")
                _run_one(db, execution)
                print(f"[worker] execution {execution.id} -> {execution.status}")
        # Progress in-flight pipelines (release ready steps, finalize) every tick.
        _advance_pipelines()
        if not ran:
            time.sleep(poll)


if __name__ == "__main__":
    main()
