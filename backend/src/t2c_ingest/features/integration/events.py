"""Catálogo de eventos de integração com o t2c_data + builders de payload (ponto 16).

Este módulo NÃO fala com o banco: só monta payloads limpos (sem segredos), resolve a CAMADA real
(bronze/silver/gold — nunca o tipo da conexão) e gera a idempotency_key de cada evento. O
`service.py` reúne os dados do banco e chama estes builders; o `outbox.py` entrega.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ─────────────────────────────── Catálogo de eventos ───────────────────────────────
# Lineage
LINEAGE_EXECUTION_RECORDED = "LINEAGE_EXECUTION_RECORDED"
# Data Quality
DATA_QUALITY_RESULT_RECORDED = "DATA_QUALITY_RESULT_RECORDED"
DATA_QUALITY_SCORE_UPDATED = "DATA_QUALITY_SCORE_UPDATED"
DATA_QUALITY_CHECK_FAILED = "DATA_QUALITY_CHECK_FAILED"
# Schema / colunas
SCHEMA_DISCOVERED = "SCHEMA_DISCOVERED"
SCHEMA_CHANGED = "SCHEMA_CHANGED"
COLUMNS_DISCOVERED = "COLUMNS_DISCOVERED"
# Data Lake / S3
S3_TABLE_UPDATED = "S3_TABLE_UPDATED"
S3_PARTITION_CREATED = "S3_PARTITION_CREATED"
S3_FILES_WRITTEN = "S3_FILES_WRITTEN"
# Incidentes operacionais
INGESTION_INCIDENT_OPENED = "INGESTION_INCIDENT_OPENED"
INGESTION_INCIDENT_RESOLVED = "INGESTION_INCIDENT_RESOLVED"
INGESTION_SLA_BREACHED = "INGESTION_SLA_BREACHED"
INGESTION_ZERO_RECORDS_DETECTED = "INGESTION_ZERO_RECORDS_DETECTED"
INGESTION_WATERMARK_STALLED = "INGESTION_WATERMARK_STALLED"

ALL_EVENT_TYPES = (
    LINEAGE_EXECUTION_RECORDED,
    DATA_QUALITY_RESULT_RECORDED, DATA_QUALITY_SCORE_UPDATED, DATA_QUALITY_CHECK_FAILED,
    SCHEMA_DISCOVERED, SCHEMA_CHANGED, COLUMNS_DISCOVERED,
    S3_TABLE_UPDATED, S3_PARTITION_CREATED, S3_FILES_WRITTEN,
    INGESTION_INCIDENT_OPENED, INGESTION_INCIDENT_RESOLVED, INGESTION_SLA_BREACHED,
    INGESTION_ZERO_RECORDS_DETECTED, INGESTION_WATERMARK_STALLED,
)

# aggregate_type de cada família de evento (para agrupar no t2c_data).
AGG_EXECUTION = "execution"
AGG_TABLE = "table"
AGG_INCIDENT = "incident"


@dataclass
class Event:
    """Envelope pronto para a outbox. `payload` já vem mascarado."""
    event_type: str
    payload: dict
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    idempotency_key: str | None = None
    occurred_at: str | None = None
    max_attempts: int = 5
    extra: dict = field(default_factory=dict)


# ─────────────────────────────── Segurança: mascaramento ───────────────────────────────
# Chaves cujo VALOR nunca pode ir no payload (nem em log). Match por substring — nenhuma chave
# legítima do domínio contém estes tokens (idempotency_key/schema_hash/partition_columns são ok).
_SECRET_TOKENS = (
    "password", "passwd", "pwd", "secret", "token", "credential", "authorization",
    "access_key", "secret_key", "private_key", "connection_string", "conn_string",
    "dsn", "api_key", "apikey", "sas_token", "account_key",
)


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(tok in k for tok in _SECRET_TOKENS)


def mask(value: Any) -> Any:
    """Remove recursivamente qualquer valor sob uma chave sensível. Nunca levanta exceção."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if _is_secret_key(str(k)):
                out[k] = "***"
            else:
                out[k] = mask(v)
        return out
    if isinstance(value, (list, tuple)):
        return [mask(v) for v in value]
    return value


def contains_secret(value: Any) -> bool:
    """Guarda de teste: True se algum valor NÃO-mascarado estiver sob chave sensível."""
    if isinstance(value, dict):
        for k, v in value.items():
            if _is_secret_key(str(k)) and v not in (None, "***", ""):
                return True
            if contains_secret(v):
                return True
    elif isinstance(value, (list, tuple)):
        return any(contains_secret(v) for v in value)
    return False


# ─────────────────────────────── Resolução de CAMADA ───────────────────────────────
# Palavras que NUNCA são camada (são tipo de conexão/destino).
_NOT_LAYER = {"s3", "postgres", "postgresql", "mysql", "sqlserver", "oracle", "datalake",
              "data_lake", "api", "csv", "parquet", "database", "storage"}
# Segmentos de path reconhecidos como camada.
_LAYER_HINTS = {"bronze", "silver", "gold", "raw", "landing", "staging", "trusted", "refined", "curated"}


def _norm_layer(v: Any) -> str | None:
    if not v:
        return None
    s = str(v).strip().lower()
    if not s or s in _NOT_LAYER:
        return None
    return s


def layer_from_path(path: str | None) -> str | None:
    """Extrai a camada de um path S3 tipo ``s3a://bucket/bronze/tabela/`` (primeiro segmento
    conhecido depois do bucket)."""
    if not path:
        return None
    try:
        from urllib.parse import urlparse
        p = urlparse(str(path))
        segs = [s for s in (p.path or "").strip("/").split("/") if s]
        # inclui o netloc? não — o bucket é o netloc; segmentos são a chave.
        for seg in segs:
            if seg.lower() in _LAYER_HINTS:
                return seg.lower()
    except Exception:  # noqa: BLE001
        return None
    return None


def resolve_layer(
    *,
    destination_layer: str | None = None,
    control_layer: str | None = None,
    control_destino: str | None = None,
    data_lake_layer: str | None = None,
    target_path: str | None = None,
) -> str | None:
    """Camada real do destino, na ordem: destination.target_layer → control.target_layer →
    control.destino (se for camada) → data_lake schema/layer → path S3 → null.

    NUNCA retorna o tipo da conexão (s3/postgres/mysql...) nem valores combinados (postgres_s3)."""
    # Campos explícitos de camada: aceitam qualquer valor que não seja tipo de conexão.
    for candidate in (destination_layer, control_layer):
        norm = _norm_layer(candidate)
        if norm:
            return norm
    # control.destino só vale se for uma CAMADA conhecida (BRONZE/SILVER/GOLD...) — nunca
    # POSTGRES_S3/S3/DATALAKE, que são tipo/rota de destino, não camada.
    cd = (control_destino or "").strip().lower()
    if cd in _LAYER_HINTS:
        return cd
    norm = _norm_layer(data_lake_layer)
    if norm:
        return norm
    return layer_from_path(target_path)


# ─────────────────────────────── Score de Data Quality ───────────────────────────────

def dq_score(checks: list[dict]) -> int:
    """Score 0-100 = % de checks relevantes (pass/fail/warn) que passaram. skip/info não contam."""
    relevant = [c for c in checks if (c.get("status") or "").lower() in ("pass", "fail", "warn")]
    if not relevant:
        return 100
    passed = sum(1 for c in relevant if (c.get("status") or "").lower() == "pass")
    return round(100 * passed / len(relevant))


def dq_status(checks: list[dict]) -> str:
    if any((c.get("status") or "").lower() == "fail" for c in checks):
        return "failed"
    if any((c.get("status") or "").lower() == "warn" for c in checks):
        return "warning"
    return "success"


def dq_severity(checks: list[dict]) -> str:
    failed = [c for c in checks if (c.get("status") or "").lower() == "fail"]
    if any((c.get("severity") or "").lower() == "critical" for c in failed):
        return "critical"
    if failed:
        return "high"
    if any((c.get("status") or "").lower() == "warn" for c in checks):
        return "medium"
    return "low"


def _clean_checks(checks: list[dict]) -> list[dict]:
    """Só os campos que o t2c_data precisa — e sem segredos."""
    out = []
    for c in checks:
        out.append({
            "name": c.get("name"),
            "status": c.get("status"),
            "severity": c.get("severity"),
            "category": c.get("category"),
            "message": c.get("detail") or c.get("message"),
            "metrics": mask(c.get("metrics") or {}),
        })
    return out


# ─────────────────────────────── Builders ───────────────────────────────

class LineageEventBuilder:
    @staticmethod
    def build(*, execution: dict, job: dict, pipeline: dict | None, source: dict, target: dict,
              metrics: dict) -> Event:
        payload = {
            "event_type": LINEAGE_EXECUTION_RECORDED,
            "execution": execution, "job": job, "pipeline": pipeline,
            "source": source, "target": target, "metrics": metrics,
        }
        return Event(
            event_type=LINEAGE_EXECUTION_RECORDED, payload=mask(payload),
            aggregate_type=AGG_EXECUTION, aggregate_id=str(execution.get("id")),
            idempotency_key=f"lineage:execution:{execution.get('id')}",
            occurred_at=execution.get("finished_at") or execution.get("started_at"),
        )


class DataQualityEventBuilder:
    @staticmethod
    def build_result(*, execution_id, control_id, job_id, pipeline_id, destination_id,
                     table_name, target: dict, checks: list[dict], executed_at: str | None) -> Event:
        score = dq_score(checks)
        status = dq_status(checks)
        severity = dq_severity(checks)
        payload = {
            "event_type": DATA_QUALITY_RESULT_RECORDED,
            "execution_id": execution_id, "control_id": control_id, "job_id": job_id,
            "pipeline_id": pipeline_id, "destination_id": destination_id,
            "table_name": table_name, "target": target,
            "quality": {"status": status, "score": score, "severity": severity,
                        "checks": _clean_checks(checks)},
            "executed_at": executed_at,
        }
        return Event(
            event_type=DATA_QUALITY_RESULT_RECORDED, payload=mask(payload),
            aggregate_type=AGG_EXECUTION, aggregate_id=str(execution_id),
            idempotency_key=f"dq:execution:{execution_id}:table:{table_name}",
            occurred_at=executed_at,
        )

    @staticmethod
    def build_score(*, execution_id, control_id, table_name, target: dict, checks: list[dict],
                    executed_at: str | None) -> Event:
        payload = {
            "event_type": DATA_QUALITY_SCORE_UPDATED,
            "execution_id": execution_id, "control_id": control_id, "table_name": table_name,
            "target": target, "score": dq_score(checks), "status": dq_status(checks),
            "executed_at": executed_at,
        }
        return Event(
            event_type=DATA_QUALITY_SCORE_UPDATED, payload=mask(payload),
            aggregate_type=AGG_TABLE, aggregate_id=str(table_name),
            idempotency_key=f"dq_score:execution:{execution_id}:table:{table_name}",
            occurred_at=executed_at,
        )

    @staticmethod
    def build_check_failed(*, execution_id, control_id, table_name, target: dict,
                           check: dict, executed_at: str | None) -> Event:
        payload = {
            "event_type": DATA_QUALITY_CHECK_FAILED,
            "execution_id": execution_id, "control_id": control_id, "table_name": table_name,
            "target": target, "check": _clean_checks([check])[0], "executed_at": executed_at,
        }
        return Event(
            event_type=DATA_QUALITY_CHECK_FAILED, payload=mask(payload),
            aggregate_type=AGG_EXECUTION, aggregate_id=str(execution_id),
            idempotency_key=f"dq:execution:{execution_id}:check:{check.get('name')}",
            occurred_at=executed_at,
        )


class SchemaEventBuilder:
    @staticmethod
    def build(*, event_type: str, table: dict, schema: dict, table_id, schema_hash: str,
              discovered_at: str | None) -> Event:
        payload = {"event_type": event_type, "table": table, "schema": schema,
                   "discovered_at": discovered_at}
        return Event(
            event_type=event_type, payload=mask(payload),
            aggregate_type=AGG_TABLE, aggregate_id=str(table_id),
            idempotency_key=f"schema:table:{table_id}:hash:{schema_hash}",
            occurred_at=discovered_at,
        )


class S3EventBuilder:
    @staticmethod
    def build_files_written(*, execution_id, job_id, control_id, table_name, layer, bucket,
                            path, partition_path, file_format, files_count, bytes_written,
                            records_written, created_at: str | None) -> Event:
        payload = {
            "event_type": S3_FILES_WRITTEN,
            "execution_id": execution_id, "job_id": job_id, "control_id": control_id,
            "table_name": table_name, "layer": layer, "bucket": bucket, "path": path,
            "partition_path": partition_path, "file_format": file_format,
            "files_count": files_count, "bytes_written": bytes_written,
            "records_written": records_written, "created_at": created_at,
        }
        pp = partition_path or "root"
        return Event(
            event_type=S3_FILES_WRITTEN, payload=mask(payload),
            aggregate_type=AGG_TABLE, aggregate_id=f"{layer or ''}.{table_name}",
            idempotency_key=f"s3:execution:{execution_id}:partition:{pp}",
            occurred_at=created_at,
        )

    @staticmethod
    def build_partition_created(*, execution_id, table_name, layer, bucket, path,
                                partition_path, partition_values, created_at: str | None) -> Event:
        payload = {
            "event_type": S3_PARTITION_CREATED,
            "execution_id": execution_id, "table_name": table_name, "layer": layer,
            "bucket": bucket, "path": path, "partition_path": partition_path,
            "partition_values": partition_values, "created_at": created_at,
        }
        pp = partition_path or "root"
        return Event(
            event_type=S3_PARTITION_CREATED, payload=mask(payload),
            aggregate_type=AGG_TABLE, aggregate_id=f"{layer or ''}.{table_name}",
            idempotency_key=f"s3_part:execution:{execution_id}:partition:{pp}",
            occurred_at=created_at,
        )


class IncidentEventBuilder:
    @staticmethod
    def build(*, event_type: str, incident_type: str, severity: str, control: dict | None,
              execution: dict | None, target: dict | None, message: str,
              error_message: str | None, opened_at: str | None,
              resolved_at: str | None = None) -> Event:
        payload = {
            "event_type": event_type,
            "incident": {"type": incident_type, "severity": severity, "message": message,
                         "error_message": error_message},
            "control": control, "execution": execution, "target": target,
            "opened_at": opened_at, "resolved_at": resolved_at,
        }
        cid = (control or {}).get("id")
        eid = (execution or {}).get("id")
        agg_id = str(eid if eid is not None else cid)
        # Idempotência: um incidente por (tipo, execução) — ou (tipo, controle) quando não há execução.
        if eid is not None:
            idem = f"incident:{incident_type}:execution:{eid}"
        else:
            idem = f"incident:{incident_type}:control:{cid}"
        if event_type == INGESTION_INCIDENT_RESOLVED:
            idem = "resolved:" + idem
        return Event(
            event_type=event_type, payload=mask(payload),
            aggregate_type=AGG_INCIDENT, aggregate_id=agg_id,
            idempotency_key=idem, occurred_at=resolved_at or opened_at,
        )
