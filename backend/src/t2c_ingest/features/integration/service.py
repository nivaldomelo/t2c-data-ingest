"""T2CDataIntegrationService — canal de metadados operacionais para o t2c_data (ponto 16).

Reúne dados do banco (execução, controle, destino, conexões, checks), monta os payloads via os
builders de events.py — com a CAMADA real (bronze/silver/gold) — e enfileira na outbox. Nada aqui
publica direto: tudo passa pela outbox transacional com retry/idempotência. Best-effort: uma falha
ao enfileirar nunca quebra a execução/o worker.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from t2c_ingest.features.integration import events as ev
from t2c_ingest.features.integration.events import (
    DataQualityEventBuilder, IncidentEventBuilder, LineageEventBuilder,
    S3EventBuilder, SchemaEventBuilder,
)
from t2c_ingest.features.integration.outbox import enqueue_event
from t2c_ingest.models.connection import Connection
from t2c_ingest.models.destination import Destination
from t2c_ingest.models.execution import Execution


def _iso(dt) -> str | None:
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _control(db: Session, execution: Execution):
    if not execution.control_id:
        return None
    try:
        from t2c_ingest.features.ingestion_control.models import IngestionControl
        return db.get(IngestionControl, execution.control_id)
    except Exception:  # noqa: BLE001
        return None


def _partition_values(partition_path: str | None) -> dict | None:
    if not partition_path:
        return None
    out = {}
    for seg in str(partition_path).strip("/").split("/"):
        if "=" in seg:
            k, v = seg.split("=", 1)
            out[k] = v
    return out or None


def _resolve_target(db: Session, execution: Execution, summary: dict, tgt: dict | None) -> dict:
    """Alvo real da carga (destino/controle/conexão), com a CAMADA correta."""
    dest = db.get(Destination, execution.destination_id) if execution.destination_id else None
    control = _control(db, execution)
    conn = None
    if execution.target_connection_id:
        conn = db.get(Connection, execution.target_connection_id)
    elif dest:
        conn = db.get(Connection, dest.connection_id)

    ttype = (summary.get("target_type") or execution.destination_type
             or (dest.destination_type if dest else None)
             or (conn.connection_type if conn else None) or (tgt or {}).get("type"))
    path = (summary.get("target_path") or (dest.target_path if dest else None)
            or (control.target_path if control else None))
    bucket = None
    if path and str(path).startswith(("s3", "s3a")):
        from urllib.parse import urlparse
        bucket = urlparse(str(path)).netloc or None
    bucket = bucket or (dest.target_bucket if dest else None) or (control.target_bucket if control else None)
    layer = ev.resolve_layer(
        destination_layer=(dest.target_layer if dest else None),
        control_layer=(control.target_layer if control else None),
        control_destino=(control.destino if control else None),
        target_path=path,
    )
    file_format = (summary.get("file_format") or (dest.file_format if dest else None)
                   or (control.file_format if control else None))
    partition_columns = ((dest.partition_columns if dest else None)
                         or (control.partition_columns if control else None))
    return {
        "destination_id": execution.destination_id,
        "connection_id": conn.id if conn else execution.target_connection_id,
        "connection_name": conn.name if conn else (tgt or {}).get("name"),
        "type": (ttype or "").lower() or None,
        "layer": layer,
        "bucket": bucket,
        "path": path,
        "database": (conn.database_name if conn else None) or (tgt or {}).get("database"),
        "schema": (dest.target_schema if dest else None) or (control.target_schema if control else None),
        "table": (dest.target_table if dest else None) or summary.get("table"),
        "file_format": file_format,
        "partition_columns": partition_columns,
        "_control": control,
    }


# ─────────────────────────────── Após execução + Data Quality ───────────────────────────────

def publish_execution_events(db: Session, execution: Execution, summary: dict,
                             src: dict | None, tgt: dict | None, checks: list[dict]) -> None:
    """Emite lineage (camada correta) + Data Quality + S3 + incidentes de uma tabela ingerida.
    Chamado pelo Data Quality, que roda ao final de cada execução. Best-effort."""
    try:
        target = _resolve_target(db, execution, summary, tgt)
        control = target.pop("_control", None)
        table_name = summary.get("table") or target.get("table")
        lidos = _to_int(summary.get("lidos"))
        gravados = _to_int(summary.get("gravados"))
        files_written = _to_int(summary.get("files_written"))
        bytes_written = _to_int(summary.get("bytes_written"))
        exec_at = _iso(execution.finished_at) or _iso(execution.started_at)

        # 1) Lineage (payload rico com destino real + camada bronze/silver/gold).
        source = {
            "connection_id": execution.source_connection_id,
            "connection_name": (src or {}).get("name"), "type": (src or {}).get("type"),
            "database": (src or {}).get("database"),
            "schema": summary.get("source_schema"), "table": table_name,
        }
        target_pub = {k: v for k, v in target.items() if not k.startswith("_")}
        lineage = LineageEventBuilder.build(
            execution={"id": execution.id, "status": (summary.get("status") or execution.status),
                       "started_at": _iso(execution.started_at), "finished_at": _iso(execution.finished_at),
                       "duration_seconds": execution.duration_seconds,
                       "tipo_ingestao": summary.get("tipo")},
            job={"id": execution.job_id, "name": execution.target_name},
            pipeline={"id": execution.pipeline_id} if execution.pipeline_id else None,
            source=source, target=target_pub,
            metrics={"records_read": lidos, "records_written": gravados,
                     "files_written": files_written, "bytes_written": bytes_written},
        )
        enqueue_event(db, lineage)

        # 2) Data Quality (resultado + score).
        dq_target = {"type": target.get("type"), "layer": target.get("layer"),
                     "bucket": target.get("bucket"), "path": target.get("path"),
                     "file_format": target.get("file_format")}
        enqueue_event(db, DataQualityEventBuilder.build_result(
            execution_id=execution.id, control_id=execution.control_id, job_id=execution.job_id,
            pipeline_id=execution.pipeline_id, destination_id=execution.destination_id,
            table_name=table_name, target=dq_target, checks=checks, executed_at=exec_at))
        enqueue_event(db, DataQualityEventBuilder.build_score(
            execution_id=execution.id, control_id=execution.control_id, table_name=table_name,
            target=dq_target, checks=checks, executed_at=exec_at))

        # 3) Checks críticos que falharam → evento por check + incidente.
        for c in checks:
            if (c.get("status") or "").lower() == "fail" and (c.get("severity") or "").lower() == "critical":
                enqueue_event(db, DataQualityEventBuilder.build_check_failed(
                    execution_id=execution.id, control_id=execution.control_id,
                    table_name=table_name, target=dq_target, check=c, executed_at=exec_at))
        crit_failed = [c for c in checks if (c.get("status") or "").lower() == "fail"
                       and (c.get("severity") or "").lower() == "critical"]
        if crit_failed:
            _incident(db, ev.INGESTION_INCIDENT_OPENED, "DATA_QUALITY_CRITICAL", "high",
                      control, execution, target,
                      message=f"Data Quality crítico falhou em {table_name}: "
                              f"{', '.join(c.get('name', '?') for c in crit_failed)}",
                      error_message=None, opened_at=exec_at)

        # 4) S3 / Data Lake: partição + arquivos.
        if (target.get("type") or "") == "s3" and target.get("path"):
            partition_path = summary.get("partition_path")
            enqueue_event(db, S3EventBuilder.build_files_written(
                execution_id=execution.id, job_id=execution.job_id, control_id=execution.control_id,
                table_name=table_name, layer=target.get("layer"), bucket=target.get("bucket"),
                path=target.get("path"), partition_path=partition_path,
                file_format=target.get("file_format"), files_count=files_written,
                bytes_written=bytes_written, records_written=gravados, created_at=exec_at))
            if partition_path:
                enqueue_event(db, S3EventBuilder.build_partition_created(
                    execution_id=execution.id, table_name=table_name, layer=target.get("layer"),
                    bucket=target.get("bucket"), path=target.get("path"),
                    partition_path=partition_path, partition_values=_partition_values(partition_path),
                    created_at=exec_at))
    except Exception as exc:  # noqa: BLE001 - integração nunca quebra o worker
        print(f"[integration] publish_execution_events skipped: {exc}")


# ─────────────────────────────── Após scan do Data Lake Catalog ───────────────────────────────

def publish_schema_events(db: Session, *, table_id, table_name: str, full_name: str,
                          layer: str | None, target_type: str, bucket: str, path: str,
                          file_format: str, columns: list[dict], partition_columns: list | None,
                          schema_hash: str, previous_hash: str | None,
                          discovered_at: str | None) -> None:
    """Emite SCHEMA_DISCOVERED/COLUMNS_DISCOVERED (e SCHEMA_CHANGED se o hash mudou). Best-effort."""
    try:
        table = {"id": table_id, "name": table_name, "full_name": full_name,
                 "layer": ev._norm_layer(layer) or ev.layer_from_path(path),
                 "type": target_type, "bucket": bucket, "path": path, "file_format": file_format}
        cols = [{"name": c.get("name") or c.get("column_name"),
                 "type": c.get("spark_type") or c.get("type"),
                 "nullable": c.get("nullable"),
                 "is_partition": c.get("is_partition", False)} for c in columns]
        schema = {"schema_hash": schema_hash, "columns_count": len(cols),
                  "partition_columns": partition_columns, "columns": cols}
        enqueue_event(db, SchemaEventBuilder.build(
            event_type=ev.SCHEMA_DISCOVERED, table=table, schema=schema, table_id=table_id,
            schema_hash=schema_hash, discovered_at=discovered_at))
        enqueue_event(db, SchemaEventBuilder.build(
            event_type=ev.COLUMNS_DISCOVERED, table=table, schema=schema, table_id=table_id,
            schema_hash=schema_hash, discovered_at=discovered_at))
        if previous_hash and previous_hash != schema_hash:
            enqueue_event(db, SchemaEventBuilder.build(
                event_type=ev.SCHEMA_CHANGED,
                table=table, schema={**schema, "previous_hash": previous_hash},
                table_id=table_id, schema_hash=schema_hash, discovered_at=discovered_at))
    except Exception as exc:  # noqa: BLE001
        print(f"[integration] publish_schema_events skipped: {exc}")


# ─────────────────────────────── Incidentes operacionais ───────────────────────────────

def _control_dict(control) -> dict | None:
    if not control:
        return None
    return {"id": control.id, "name": control.nome_tabela, "owner_name": control.owner_name,
            "criticality": control.criticality, "group": control.grupo}


def _incident(db: Session, event_type: str, incident_type: str, severity: str, control,
              execution, target: dict | None, *, message: str, error_message: str | None,
              opened_at: str | None, resolved_at: str | None = None) -> None:
    exec_dict = None
    if execution is not None:
        exec_dict = {"id": execution.id, "status": execution.status,
                     "duration_seconds": execution.duration_seconds}
    tgt = None
    if target:
        tgt = {"destination_id": target.get("destination_id"), "type": target.get("type"),
               "layer": target.get("layer"), "path": target.get("path")}
    enqueue_event(db, IncidentEventBuilder.build(
        event_type=event_type, incident_type=incident_type, severity=severity,
        control=_control_dict(control), execution=exec_dict, target=tgt,
        message=message, error_message=error_message, opened_at=opened_at, resolved_at=resolved_at))


def publish_operational_incidents(db: Session) -> int:
    """Detecta e publica incidentes operacionais (SLA/zero registros/watermark parado) a partir
    das MESMAS consultas da Observabilidade. Idempotente por (tipo, execução): reexecutar não
    duplica. Chamado a cada tick do worker. Best-effort — retorna quantos foram enfileirados."""
    try:
        from t2c_ingest.features.observability import service as obs
    except Exception:  # noqa: BLE001
        return 0
    n = 0
    now = datetime.now(timezone.utc).isoformat()
    try:
        for b in obs.sla_breaches(db):
            _incident_from_obs(db, ev.INGESTION_SLA_BREACHED, "SLA_BREACH", "high", b,
                               f"Carga {b.get('carga')} excedeu o SLA de {b.get('sla_minutes')}min "
                               f"(durou {b.get('duration_seconds')}s).", now)
            n += 1
        for z in obs.zero_records(db):
            if z.get("classificacao") in ("atencao", "critico"):
                sev = "high" if z.get("classificacao") == "critico" else "medium"
                _incident_from_obs(db, ev.INGESTION_ZERO_RECORDS_DETECTED, "ZERO_RECORDS", sev, z,
                                   f"Carga {z.get('carga')} concluiu com zero registros "
                                   f"({z.get('classificacao')}).", now)
                n += 1
        for w in obs.watermark_stalled(db):
            sev = "high" if w.get("criticidade") in ("alta", "critica") else "medium"
            _incident_from_obs(db, ev.INGESTION_WATERMARK_STALLED, "WATERMARK_STALLED", sev, w,
                               f"Watermark da carga {w.get('carga')} não avançou na última execução.", now)
            n += 1
        if n:
            db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[integration] operational incidents skipped: {exc}")
        return 0
    return n


def _incident_from_obs(db: Session, event_type: str, incident_type: str, severity: str,
                       obs_row: dict, message: str, opened_at: str) -> None:
    control = {"id": obs_row.get("control_id"), "name": obs_row.get("carga"),
               "owner_name": obs_row.get("owner"), "criticality": obs_row.get("criticidade"),
               "group": obs_row.get("grupo")}
    execution = {"id": obs_row.get("execution_id")} if obs_row.get("execution_id") else None
    enqueue_event(db, IncidentEventBuilder.build(
        event_type=event_type, incident_type=incident_type, severity=severity,
        control=control, execution=execution, target=None,
        message=message, error_message=None, opened_at=opened_at))
