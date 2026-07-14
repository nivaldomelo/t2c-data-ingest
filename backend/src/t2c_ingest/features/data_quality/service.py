"""Data quality evaluation + lineage push to t2c_data.

Runs when a job execution finishes: derives checks from the worker's INGEST_SUMMARY (stored in
`execution.final_message`) and the connection lines in the logs, records a `dq_results` row, and
writes an operational lineage row into the reference schema (t2c_data.ingest_lineage) so the base
product can build lineage/metadata from real ingest runs. Best-effort — never breaks the worker.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.core.config import settings
from t2c_ingest.features.data_quality import reconciliation
from t2c_ingest.features.executions.log_parser import parse_connections, parse_ingest_summary
from t2c_ingest.models.data_quality import DqResult
from t2c_ingest.models.execution import Execution, ExecutionLog


def _to_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _overall(checks: list[dict]) -> str:
    if any(c["status"] == "fail" for c in checks):
        return "fail"
    if any(c["status"] == "warn" for c in checks):
        return "warn"
    return "pass"


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

    return checks, _overall(checks)


def _resolve_pk(db: Session, table: str | None, source_type: str | None, target_type: str | None) -> list[str]:
    """Primary-key columns for ``table`` from the control table (``colunas_chave``).

    A table may appear under several routes (e.g. POSTGRES->BRONZE and POSTGRES->MYSQL) with
    different keys; prefer the row whose origem/destino matches this job's connections, so we
    validate the key actually used for THIS target.
    """
    if not table:
        return []
    try:
        from t2c_ingest.features.ingestion_control.models import IngestionControl

        rows = db.execute(
            select(IngestionControl.colunas_chave, IngestionControl.origem, IngestionControl.destino)
            .where(IngestionControl.nome_tabela == table)
        ).all()
        if not rows:
            return []
        raw = None
        st, tt = (source_type or "").upper(), (target_type or "").upper()
        for chave, origem, destino in rows:
            if st and (origem or "").upper() == st and tt and (destino or "").upper() == tt:
                raw = chave
                break
        if raw is None:
            raw = rows[0][0]  # fall back to the first defined key
        return [c.strip() for c in (raw or "").split(",") if c.strip()]
    except Exception:  # noqa: BLE001
        return []


def _reconcile(db: Session, execution: Execution, summary: dict) -> list[dict]:
    """Best-effort real reconciliation against the source/target DBs. Never raises."""
    if not settings.dq_reconcile_enabled:
        return []
    try:
        from t2c_ingest.features.connections.repository import get_connection_by_ref
        from t2c_ingest.features.connections.worker_support import _extract_refs
        from t2c_ingest.models.job import JobDefinition

        job = db.get(JobDefinition, execution.job_id) if execution.job_id else None
        refs = _extract_refs(job.arguments if job else [])
        source_conn = get_connection_by_ref(db, refs["SOURCE_"]) if "SOURCE_" in refs else None
        target_conn = get_connection_by_ref(db, refs["TARGET_"]) if "TARGET_" in refs else None

        # The INGEST_SUMMARY table is the source table; the controlled ingest writes to the same
        # schema.table name on the target (see postgres_to_mysql_controlled_ingest).
        table = summary.get("table")
        pk = _resolve_pk(
            db, table,
            source_conn.connection_type if source_conn else None,
            target_conn.connection_type if target_conn else None,
        )
        return reconciliation.run(
            source_conn, table, target_conn, table, pk, summary.get("tipo"),
        )
    except Exception as exc:  # noqa: BLE001 - reconciliation must never break the run
        print(f"[dq] reconciliation skipped: {exc}")
        return []


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
    agg_overall = "pass"
    tables_summary = []
    for summary in summaries:
        checks, overall = _evaluate_checks(summary)
        recon = _reconcile(db, execution, summary)
        if recon:
            checks = checks + recon
        # Data Lake S3 (ponto 15): partição/arquivos/parquet/colunas/registros/watermark.
        try:
            from t2c_ingest.features.data_quality import s3_checks
            if s3_checks.is_s3_target(db, execution, summary):
                checks = checks + s3_checks.evaluate(db, execution, summary)
        except Exception as exc:  # noqa: BLE001 - DQ S3 nunca quebra a execução
            print(f"[dq] s3 checks skipped: {exc}")
        overall = _overall(checks)
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
        tables_summary.append({"table": summary.get("table"), "overall": overall})
        if overall == "fail":
            agg_overall = "fail"
        elif overall == "warn" and agg_overall != "fail":
            agg_overall = "warn"
        _maybe_alert_dq(db, execution, summary, checks)
        _write_lineage(db, execution, summary, src, tgt, lidos, gravados)
    # Resumo de qualidade first-class na execução (observabilidade).
    execution.quality_summary = {"overall": agg_overall, "tables": tables_summary}
    db.commit()
    return first_result


def _maybe_alert_dq(db: Session, execution: Execution, summary: dict, checks: list[dict]) -> None:
    """Alerta em falha crítica de DQ (S3 sobretudo): partição/arquivo ausente, parquet ilegível,
    coluna obrigatória faltando, full com zero registros. Best-effort."""
    critical = [c for c in checks if c.get("status") == "fail" and c.get("severity") == "critical"]
    if not critical:
        return
    try:
        from t2c_ingest.features.alerts.service import emit
        names = ", ".join(c["name"] for c in critical)
        emit(db, event_type="JOB_ZERO_RECORDS" if any("RECORDS" in c["name"] for c in critical) else "JOB_FAILED",
             severity="critical",
             title=f"Data Quality falhou: {summary.get('table') or execution.target_name}",
             message=(f"Checks críticos falharam em {summary.get('table')}: {names}. "
                      f"Execução #{execution.id}.")[:1000],
             job_id=execution.job_id, execution_id=execution.id)
    except Exception as exc:  # noqa: BLE001
        print(f"[dq] alert skipped: {exc}")


def _write_lineage(db: Session, execution: Execution, summary: dict, src, tgt, lidos, gravados) -> None:
    """Enqueue an operational lineage row for reliable delivery to t2c_data (via the outbox).

    Written in the same transaction as the DqResult, so the lineage is never lost; the worker's
    publisher delivers it to t2c_data with retry and alerts on persistent failure.
    """
    try:
        from t2c_ingest.features.integration.outbox import enqueue

        exec_at = execution.finished_at or datetime.now(timezone.utc)
        enqueue(db, "lineage", {
            "eid": execution.id, "jid": execution.job_id, "jname": execution.target_name,
            "pid": execution.pipeline_id,
            "sconn": (src or {}).get("name"), "stype": (src or {}).get("type"),
            "tconn": (tgt or {}).get("name"), "ttype": (tgt or {}).get("type"),
            "tsource": summary.get("table"), "ttarget": (tgt or {}).get("database"),
            "camada": (tgt or {}).get("type"),
            "rr": lidos, "rw": gravados, "tipo": summary.get("tipo"),
            "status": summary.get("status"),
            "exec_at": exec_at.isoformat(),
        })
    except Exception as exc:  # noqa: BLE001 - enqueue must never break the run
        print(f"[dq] lineage enqueue skipped: {exc}")
