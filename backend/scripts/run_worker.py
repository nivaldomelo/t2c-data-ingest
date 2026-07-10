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
import signal
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
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


_WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _lease_until() -> datetime:
    return _now() + timedelta(seconds=settings.worker_lease_ttl_seconds)


def _log(db, execution_id: int, seq: int, level: str, message: str) -> int:
    from t2c_ingest.core.log_masking import mask_secrets

    db.add(
        ExecutionLog(
            execution_id=execution_id,
            seq=seq,
            level=level,
            message=mask_secrets(message)[:100_000],
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
    execution.worker_id = _WORKER_ID
    execution.heartbeat_at = _now()
    execution.lease_expires_at = _lease_until()
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


def _build_command(job: JobDefinition, env_keys: list[str] | None = None) -> list[str]:
    args = [str(a) for a in (job.arguments or [])]
    if job.type in {"spark_python", "spark_submit"}:
        container = settings.runtime_spark_submit_container
        if container and settings.spark_submit_via_container:
            return _container_spark_command(job, args, env_keys or [], container)
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


def _container_spark_command(job: JobDefinition, args: list[str], env_keys: list[str], container: str) -> list[str]:
    """spark-submit INSIDE a Spark container (via docker exec) so the driver's Python matches the
    executors. JDBC jars are baked into the image (/opt/spark/jars). Env (incl. secrets) is passed
    with `docker exec -e KEY` (read from the worker's process env — never on the command line)."""
    import shlex

    parts = [
        "/opt/spark/bin/spark-submit",
        "--master", shlex.quote(settings.spark_master_url),
        "--driver-memory", shlex.quote(settings.spark_driver_memory),
        "--conf", "spark.driver.host=$(hostname)",
        "--conf", "spark.pyspark.python=/usr/bin/python3",
        "--conf", "spark.pyspark.driver.python=/usr/bin/python3",
        "--conf", f"spark.executor.memory={shlex.quote(settings.spark_executor_memory)}",
        "--conf", "spark.executor.cores=1",
        "--conf", "spark.deploy.spreadOut=true",
        "--conf", "spark.driver.extraJavaOptions=-Djava.net.preferIPv4Stack=true",
        "--conf", "spark.executor.extraJavaOptions=-Djava.net.preferIPv4Stack=true",
    ]
    if job.type == "spark_submit" and job.main_class:
        parts += ["--class", shlex.quote(job.main_class)]
    parts += [shlex.quote(job.script_path or "")] + [shlex.quote(a) for a in args]
    submit = " ".join(parts)
    exec_env = []
    for k in env_keys:
        exec_env += ["-e", k]  # pass value through from our env; keeps secrets off the cmdline
    return ["docker", "exec", *exec_env, container, "bash", "-lc", submit]


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

    started = time.monotonic()
    try:
        # Env precedence: process env <- variables <- job.env_vars <- resolved connection creds.
        from t2c_ingest.features.variables.service import resolve_runtime_variables

        var_items = resolve_runtime_variables(db, job.id)
        env = {**_os_environ()}
        env.update({k: v for k, v, _ in var_items})  # reusable variables (lowest precedence)
        env.update({k: str(v) for k, v in (job.env_vars or {}).items()})
        env.update(connection_env)  # SOURCE_*/TARGET_* (includes decrypted passwords)
        # Build the command AFTER env so a container submit can pass env keys via docker exec -e.
        cmd = _build_command(job, list(env.keys()))
        # Stamp the runtime stack that runs this job (Spark jobs run on the Spark 4 image).
        if job.type in {"spark_python", "spark_submit"}:
            execution.spark_version = settings.spark_version
            execution.python_version = settings.spark_python_version
            execution.runtime_image = settings.runtime_worker_image_tag
        seq = _log(db, execution.id, seq, "INFO", f"$ {_redact(cmd)}")
        # Exact secret values to redact from captured output (connection creds + secret vars).
        from t2c_ingest.core.log_masking import mask_secrets

        secret_values = [v for k, v in connection_env.items() if "PASSWORD" in k.upper() and v]
        secret_values += [v for _, v, is_secret in var_items if is_secret and v]
        stdout, stderr, returncode, outcome = _run_subprocess(db, execution, cmd, env, job)
        stdout = mask_secrets(stdout, secret_values)
        stderr = mask_secrets(stderr, secret_values)
        if stdout:
            seq = _log(db, execution.id, seq, "INFO", stdout)
        if stderr:
            seq = _log(db, execution.id, seq, "ERROR" if returncode else "WARNING", stderr)
        duration = int(time.monotonic() - started)
        execution.duration_seconds = duration
        if outcome == "cancelled":
            execution.status = "cancelled"
            execution.final_message = execution.final_message or "Cancelado durante a execução"
            _log(db, execution.id, seq, "WARNING", "Execução cancelada")
        elif outcome == "timeout":
            execution.status = "timeout"
            execution.final_message = f"Timed out after {job.timeout_seconds}s"
            _log(db, execution.id, seq, "ERROR", "Execution timed out")
        elif returncode == 0:
            execution.status = "success"
            execution.final_message = "Completed successfully"
            _capture_summary(db, execution, stdout or "")
        else:
            execution.status = "failed"
            execution.final_message = f"Exited with code {returncode}"
            execution.error_trace = (stderr or "")[:20000]
    except Exception as exc:  # noqa: BLE001
        execution.status = "failed"
        execution.final_message = str(exc)
        execution.error_trace = repr(exc)
        execution.duration_seconds = int(time.monotonic() - started)
        _log(db, execution.id, seq, "ERROR", repr(exc))
    finally:
        execution.finished_at = _now()
        execution.lease_expires_at = None
        db.commit()
        _evaluate_data_quality(db, execution)
        _emit_execution_alert(db, execution)
        _maybe_retry(db, execution)


def _run_subprocess(db, execution: Execution, cmd: list[str], env: dict, job: JobDefinition):
    """Run the job as a child process group, refreshing the lease and honoring cancellation and
    timeout while it runs. Returns (stdout, stderr, returncode, outcome) where outcome is one of
    'done' | 'cancelled' | 'timeout'. Output goes to temp files to avoid pipe-buffer deadlock."""
    # Per-step timeout (from a pipeline step) overrides the job's default when present.
    step_timeout = (execution.parameters or {}).get("_timeout_seconds")
    timeout_s = int(step_timeout) if step_timeout else (job.timeout_seconds or None)
    hb = max(3, int(settings.worker_heartbeat_seconds or 20))
    started = time.monotonic()
    outcome = "done"
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as out_f, \
         tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as err_f:
        proc = subprocess.Popen(  # noqa: S603 - argv list, no shell
            cmd, stdout=out_f, stderr=err_f, env=env, start_new_session=True,
        )
        while True:
            try:
                proc.wait(timeout=hb)
                break
            except subprocess.TimeoutExpired:
                _touch_lease(db, execution)
                if timeout_s and (time.monotonic() - started) > timeout_s:
                    _terminate(proc)
                    outcome = "timeout"
                    break
                if _cancel_requested(db, execution):
                    _terminate(proc)
                    outcome = "cancelled"
                    break
        out_f.seek(0)
        err_f.seek(0)
        return out_f.read(), err_f.read(), proc.returncode, outcome


def _terminate(proc: subprocess.Popen) -> None:
    """Stop the whole process group (SIGTERM, then SIGKILL)."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(proc.pid), sig)
            proc.wait(timeout=10)
            return
        except (ProcessLookupError, PermissionError):
            return
        except Exception:  # noqa: BLE001
            continue


def _touch_lease(db, execution: Execution) -> None:
    try:
        db.query(Execution).filter(Execution.id == execution.id).update(
            {"heartbeat_at": _now(), "lease_expires_at": _lease_until()}
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


def _cancel_requested(db, execution: Execution) -> bool:
    try:
        return bool(db.scalar(select(Execution.cancel_requested).where(Execution.id == execution.id)))
    except Exception:  # noqa: BLE001
        db.rollback()
        return False


def _maybe_retry(db, execution: Execution) -> None:
    """Enqueue a retry for a failed job execution if attempts remain."""
    try:
        if execution.status != "failed":
            return
        from t2c_ingest.services.execution_service import enqueue_retry

        retry = enqueue_retry(db, execution)
        if retry is not None:
            db.commit()
            print(f"[worker] execution {execution.id} failed -> retry {retry.id} (attempt {retry.attempt})")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[worker] retry error for execution {execution.id}: {exc}")


def _evaluate_data_quality(db, execution) -> None:
    """Compute DQ checks + push lineage to t2c_data for a finished job execution."""
    try:
        from t2c_ingest.features.data_quality.service import evaluate_execution

        if execution.status in ("success", "failed"):
            evaluate_execution(db, execution)
    except Exception as exc:  # noqa: BLE001
        print(f"[worker] data-quality error: {exc}")


def _emit_execution_alert(db, execution) -> None:
    """Raise an alert when a job execution fails/times out, or succeeds with zero records."""
    try:
        from t2c_ingest.features.alerts.service import emit

        if execution.status in ("failed", "timeout"):
            emit(db, event_type="JOB_FAILED", severity="critical",
                 title=f"Job falhou: {execution.target_name or execution.job_id}",
                 message=(execution.final_message or "Execução falhou.")[:1000],
                 job_id=execution.job_id, execution_id=execution.id)
            db.commit()
        elif execution.status == "success" and execution.final_message:
            fm = execution.final_message
            if "lidos=0" in fm and "gravados=0" in fm:
                emit(db, event_type="JOB_ZERO_RECORDS", severity="warning",
                     title=f"Carga com zero registros: {execution.target_name or execution.job_id}",
                     message=fm[:1000], job_id=execution.job_id, execution_id=execution.id)
                db.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"[worker] alert emit error: {exc}")


def _dispatch_alerts() -> None:
    """Deliver pending alert notifications to their channels."""
    try:
        from t2c_ingest.features.alerts.service import dispatch_pending

        with SessionLocal() as db:
            dispatch_pending(db)
    except Exception as exc:  # noqa: BLE001
        print(f"[worker] alert dispatch error: {exc}")


# Keys that must NEVER reach a job subprocess: the JWT signing secret and the Fernet key used
# to encrypt every connection password would let a job forge admin tokens and decrypt all
# stored secrets (and the job's stdout is captured verbatim into execution logs). No job needs
# them. DATABASE_URL is intentionally kept: the control-table-driven ingest reads it.
_SECRET_ENV_EXACT = {"JWT_SECRET_KEY", "CONNECTION_SECRET_KEY"}
_SECRET_ENV_MARKERS = (
    "SECRET", "TOKEN", "PRIVATE_KEY", "PASSWORD", "PASSWD",
    "CREDENTIAL", "API_KEY", "APIKEY", "ACCESS_KEY",
)


def _os_environ() -> dict:
    """Base environment for job subprocesses, with the backend's own secrets stripped."""
    clean: dict = {}
    for k, v in os.environ.items():
        up = k.upper()
        if up in _SECRET_ENV_EXACT or any(m in up for m in _SECRET_ENV_MARKERS):
            continue
        clean[k] = v
    return clean


def _advance_pipelines() -> None:
    """Progress running pipeline executions (release ready steps, finalize)."""
    try:
        from t2c_ingest.features.pipelines.runner import advance_pipeline_executions

        with SessionLocal() as db:
            advance_pipeline_executions(db)
    except Exception as exc:  # noqa: BLE001 - never let orchestration kill the worker loop
        print(f"[worker] pipeline advance error: {exc}")


def _advance_backfills() -> None:
    """Roll up backfill run statuses once their executions/pipelines finish."""
    try:
        from t2c_ingest.features.backfill.service import advance_backfills

        with SessionLocal() as db:
            advance_backfills(db)
    except Exception as exc:  # noqa: BLE001 - never let it kill the worker loop
        print(f"[worker] backfill advance error: {exc}")


def _process_library_actions() -> bool:
    """Claim and run one queued cluster-library action (pip install/uninstall/reinstall)."""
    try:
        from t2c_ingest.features.cluster_libraries.service import run_action
        from t2c_ingest.models.cluster_library import ClusterLibraryAction

        with SessionLocal() as db:
            action = db.scalar(
                select(ClusterLibraryAction)
                .where(ClusterLibraryAction.status == "queued")
                .order_by(ClusterLibraryAction.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if action is None:
                return False
            print(f"[worker] library action {action.id}: {action.action} {action.package_spec}")
            run_action(db, action)
            print(f"[worker] library action {action.id} -> {action.status}")
            return True
    except Exception as exc:  # noqa: BLE001 - never let a library action kill the worker loop
        print(f"[worker] library action error: {exc}")
        return False


def _process_runtime_jobs() -> bool:
    """Claim and run one queued runtime build or validation (image build / cluster validation)."""
    ran = False
    try:
        from t2c_ingest.features.runtime.service import run_build, run_validation
        from t2c_ingest.models.runtime import RuntimeBuild, RuntimeValidation

        with SessionLocal() as db:
            build = db.scalar(
                select(RuntimeBuild).where(RuntimeBuild.status == "queued")
                .order_by(RuntimeBuild.id).with_for_update(skip_locked=True).limit(1)
            )
            if build is not None:
                print(f"[worker] runtime build {build.id} ({build.image_full_name})")
                run_build(db, build)
                print(f"[worker] runtime build {build.id} -> {build.status}")
                return True
        with SessionLocal() as db:
            val = db.scalar(
                select(RuntimeValidation).where(RuntimeValidation.status == "queued")
                .order_by(RuntimeValidation.id).with_for_update(skip_locked=True).limit(1)
            )
            if val is not None:
                print(f"[worker] runtime validation {val.id} ({val.validation_type})")
                run_validation(db, val)
                print(f"[worker] runtime validation {val.id} -> {val.status}")
                return True
    except Exception as exc:  # noqa: BLE001 - never let a runtime job kill the worker loop
        print(f"[worker] runtime job error: {exc}")
    return ran


def _reap_stale_executions() -> None:
    """Fail (and retry) executions whose worker died — their lease expired while 'running'."""
    try:
        with SessionLocal() as db:
            now = _now()
            stale = db.scalars(
                select(Execution).where(
                    Execution.status == "running",
                    Execution.lease_expires_at.is_not(None),
                    Execution.lease_expires_at < now,
                ).limit(20)
            ).all()
            for ex in stale:
                ex.status = "failed"
                ex.final_message = f"Execução órfã: worker {ex.worker_id} perdeu o lease"
                ex.finished_at = now
                ex.lease_expires_at = None
                db.commit()
                print(f"[worker] reaped stale execution {ex.id} (worker {ex.worker_id})")
                _emit_execution_alert(db, ex)
                _maybe_retry(db, ex)
    except Exception as exc:  # noqa: BLE001
        print(f"[worker] reaper error: {exc}")


_last_retention = 0.0


def _maybe_run_retention() -> None:
    global _last_retention
    interval = settings.retention_interval_seconds
    now = time.monotonic()
    if now - _last_retention < interval:
        return
    _last_retention = now
    try:
        from t2c_ingest.services.retention import run_retention

        with SessionLocal() as db:
            summary = run_retention(db)
        if summary:
            print(f"[retention] pruned: {summary}")
    except Exception as exc:  # noqa: BLE001
        print(f"[retention] error: {exc}")


# Postgres advisory-lock key that serializes ORCHESTRATION across worker replicas. Job
# execution itself stays concurrent (SKIP LOCKED); only the shared orchestration below runs on
# a single worker at a time, so scaling to N workers cannot double-release a pipeline step,
# double-dispatch an alert or double-roll a backfill.
_ORCH_LOCK_KEY = 728411001


def _run_orchestration() -> bool:
    """Run the shared orchestration under an advisory lock. Returns True if any work happened.
    A worker that can't get the lock simply skips (another worker is orchestrating)."""
    from sqlalchemy import text

    ran = False
    with SessionLocal() as lockdb:
        got = lockdb.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _ORCH_LOCK_KEY}).scalar()
        if not got:
            return False
        try:
            _advance_pipelines()      # release ready steps, finalize pipelines
            _advance_backfills()      # roll up backfill status
            _dispatch_alerts()        # deliver queued notifications
            if _process_library_actions():
                ran = True
            if _process_runtime_jobs():
                ran = True
            _reap_stale_executions()  # recover orphaned runs
            _maybe_run_retention()    # prune old rows (interval-guarded)
            try:
                from t2c_ingest.features.integration.outbox import publish_pending

                with SessionLocal() as odb:
                    publish_pending(odb)         # deliver queued t2c_data pushes (retry/alert)
            except Exception as exc:  # noqa: BLE001
                print(f"[worker] outbox publish error: {exc}")
            try:
                from t2c_ingest.features.alerts.monitors import check_schedule_overdue

                check_schedule_overdue(lockdb)   # alert if a schedule is overdue (scheduler stuck)
            except Exception as exc:  # noqa: BLE001
                print(f"[worker] overdue monitor error: {exc}")
        finally:
            lockdb.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _ORCH_LOCK_KEY})
    return ran


def main() -> None:
    from t2c_ingest.core.bootstrap import enforce_secure_config

    enforce_secure_config()  # refuse to run under insecure prod defaults (worker decrypts secrets)
    poll = settings.worker_poll_interval_seconds
    print(f"[worker] started ({_WORKER_ID}); polling every {poll}s; spark master={settings.spark_master_url}")
    while True:
        ran = False
        # Liveness heartbeat (each tick, outside the orchestration lock) so the scheduler can
        # detect this worker dying even when another replica holds the orchestration lock.
        try:
            from t2c_ingest.features.alerts.monitors import heartbeat_worker

            with SessionLocal() as hb:
                heartbeat_worker(hb, _WORKER_ID)
        except Exception:  # noqa: BLE001
            pass
        # Job execution: concurrent across replicas (each row claimed once via SKIP LOCKED).
        with SessionLocal() as db:
            execution = _claim_next(db)
            if execution is not None:
                ran = True
                print(f"[worker] running execution {execution.id} ({execution.target_name})")
                _run_one(db, execution)
                print(f"[worker] execution {execution.id} -> {execution.status}")
        # Orchestration: serialized across replicas via advisory lock.
        if _run_orchestration():
            ran = True
        if not ran:
            time.sleep(poll)


if __name__ == "__main__":
    main()
