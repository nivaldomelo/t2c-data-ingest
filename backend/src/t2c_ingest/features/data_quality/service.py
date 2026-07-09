"""Data quality evaluation + lineage push to t2c_data.

Runs when a job execution finishes: derives checks from the worker's INGEST_SUMMARY (stored in
`execution.final_message`) and the connection lines in the logs, records a `dq_results` row, and
writes an operational lineage row into the reference schema (t2c_data.ingest_lineage) so the base
product can build lineage/metadata from real ingest runs. Best-effort — never breaks the worker.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.features.executions.log_parser import parse_connections, parse_ingest_summary
from t2c_ingest.models.data_quality import DqResult
from t2c_ingest.models.execution import Execution, ExecutionLog


def _to_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _evaluate_checks(summary: dict) -> tuple[list[dict], str]:
    lidos = _to_int(summary.get("lidos"))
    gravados = _to_int(summary.get("gravados"))
    tipo = (summary.get("tipo") or "").upper()
    status = (summary.get("status") or "").upper()
    checks: list[dict] = []

    # Registros lidos > 0.
    checks.append({
        "name": "registros_lidos", "status": "pass" if (lidos or 0) > 0 else "warn",
        "detail": f"lidos={lidos}",
    })
    # Gravados x lidos (full: iguais; incremental: gravados <= lidos).
    if lidos is not None and gravados is not None:
        if tipo == "FULL":
            checks.append({"name": "gravados_vs_lidos", "status": "pass" if gravados == lidos else "fail",
                           "detail": f"FULL: gravados={gravados} lidos={lidos}"})
        else:
            checks.append({"name": "gravados_vs_lidos", "status": "pass" if gravados <= lidos else "warn",
                           "detail": f"{tipo or 'INCREMENTAL'}: gravados={gravados} lidos={lidos}"})
    # Watermark avançou (incremental).
    if tipo == "INCREMENTAL":
        novo = summary.get("watermark_novo")
        checks.append({
            "name": "watermark_avancou",
            "status": "pass" if novo else "warn",
            "detail": "novo watermark aplicado" if novo else "watermark mantido (sem novos registros)",
        })
    # Status reportado pelo job.
    checks.append({"name": "status_job", "status": "pass" if status.startswith("SUC") else "fail",
                   "detail": f"status={summary.get('status')}"})

    overall = "fail" if any(c["status"] == "fail" for c in checks) else (
        "warn" if any(c["status"] == "warn" for c in checks) else "pass")
    return checks, overall


def evaluate_execution(db: Session, execution: Execution) -> DqResult | None:
    """Evaluate DQ for a finished job execution and persist a result + lineage PER table.

    A job may ingest several tables (multiple INGEST_SUMMARY lines); we record one dq_results +
    one lineage row for each. Falls back to final_message when no summary line is in the logs.
    """
    if execution.target_type != "job":
        return None
    if db.scalar(select(DqResult.id).where(DqResult.execution_id == execution.id).limit(1)):
        return None  # already evaluated

    logs_text = "\n".join(
        m for (m,) in db.execute(
            select(ExecutionLog.message).where(ExecutionLog.execution_id == execution.id).order_by(ExecutionLog.seq, ExecutionLog.id)
        ).all()
    )
    # One summary per INGEST_SUMMARY line; fall back to final_message.
    summaries = []
    for line in logs_text.splitlines():
        if "INGEST_SUMMARY" in line:
            s = parse_ingest_summary(line)
            if s:
                summaries.append(s)
    if not summaries and execution.final_message:
        s = parse_ingest_summary("INGEST_SUMMARY: " + execution.final_message)
        if s:
            summaries.append(s)
    if not summaries:
        return None

    src, tgt = parse_connections(logs_text)
    first_result = None
    for summary in summaries:
        checks, overall = _evaluate_checks(summary)
        lidos = _to_int(summary.get("lidos"))
        gravados = _to_int(summary.get("gravados"))
        result = DqResult(
            execution_id=execution.id, job_id=execution.job_id, job_name=execution.target_name,
            table_name=summary.get("table"), tipo_ingestao=summary.get("tipo"),
            records_read=lidos, records_written=gravados,
            watermark_before=summary.get("watermark_anterior"), watermark_after=summary.get("watermark_novo"),
            checks=checks, overall=overall,
        )
        db.add(result)
        first_result = first_result or result
        _write_lineage(db, execution, summary, src, tgt, lidos, gravados)
    db.commit()
    return first_result


def _write_lineage(db: Session, execution: Execution, summary: dict, src, tgt, lidos, gravados) -> None:
    """Insert an operational lineage row into the reference schema (t2c_data)."""
    r = settings.reference_schema or "t2c_data"
    try:
        db.execute(text(f"""
            INSERT INTO "{r}".ingest_lineage
              (execution_id, job_id, job_name, pipeline_id, source_connection, source_type,
               target_connection, target_type, table_source, table_target, camada,
               records_read, records_written, tipo_ingestao, status, executed_at)
            VALUES
              (:eid, :jid, :jname, :pid, :sconn, :stype, :tconn, :ttype, :tsource, :ttarget, :camada,
               :rr, :rw, :tipo, :status, :exec_at)
        """), {
            "eid": execution.id, "jid": execution.job_id, "jname": execution.target_name,
            "pid": execution.pipeline_id,
            "sconn": (src or {}).get("name"), "stype": (src or {}).get("type"),
            "tconn": (tgt or {}).get("name"), "ttype": (tgt or {}).get("type"),
            "tsource": summary.get("table"), "ttarget": (tgt or {}).get("database"),
            "camada": (tgt or {}).get("type"),
            "rr": lidos, "rw": gravados, "tipo": summary.get("tipo"),
            "status": summary.get("status"),
            "exec_at": execution.finished_at or datetime.now(timezone.utc),
        })
    except Exception as exc:  # noqa: BLE001 - lineage push must never break the run
        print(f"[dq] lineage write skipped: {exc}")
