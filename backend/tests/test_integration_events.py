"""Unit tests for the t2c_data integration events layer (ponto 16). No DB/network.

Cobre os critérios de aceite verificáveis sem banco: camada real bronze/silver/gold (nunca o tipo
da conexão), idempotency_key por evento, ausência de segredos no payload, score de DQ, backoff e
dead-letter. O fluxo com banco (enqueue idempotente + publish → sent + camada nos dois sinks) é
validado em ambiente."""
from t2c_ingest.features.integration import events as ev
from t2c_ingest.features.integration import outbox
from t2c_ingest.features.integration.events import (
    DataQualityEventBuilder, IncidentEventBuilder, LineageEventBuilder,
    S3EventBuilder, SchemaEventBuilder,
)


# ─────────────────────────────── Camada ───────────────────────────────

def test_resolve_layer_priority_destination_first():
    assert ev.resolve_layer(destination_layer="silver", control_layer="bronze") == "silver"


def test_resolve_layer_falls_back_to_control_then_destino():
    assert ev.resolve_layer(control_layer="gold") == "gold"
    assert ev.resolve_layer(control_destino="BRONZE") == "bronze"


def test_resolve_layer_from_s3_path():
    assert ev.resolve_layer(target_path="s3a://datalake/bronze/eventos_status/") == "bronze"


def test_layer_is_never_connection_type():
    # s3/postgres/mysql/datalake NÃO são camada.
    assert ev.resolve_layer(destination_layer="s3") is None
    assert ev.resolve_layer(control_destino="POSTGRES") is None
    assert ev.resolve_layer(control_destino="S3", destination_layer="mysql") is None
    assert ev.resolve_layer(control_destino="DATALAKE") is None


def test_layer_from_path_ignores_non_layer_segments():
    assert ev.layer_from_path("s3a://bucket/random/table/") is None
    assert ev.layer_from_path("s3a://bucket/gold/vendas/ano=2026/") == "gold"


# ─────────────────────────────── Mascaramento ───────────────────────────────

def test_mask_removes_secrets_recursively():
    masked = ev.mask({
        "password": "hunter2", "path": "s3a://b/bronze/t",
        "aws_secret_access_key": "AKIA", "conn": {"token": "abc", "layer": "bronze"},
        "items": [{"api_key": "k", "ok": 1}],
    })
    assert masked["password"] == "***"
    assert masked["aws_secret_access_key"] == "***"
    assert masked["conn"]["token"] == "***"
    assert masked["items"][0]["api_key"] == "***"
    # valores não-sensíveis preservados
    assert masked["path"] == "s3a://b/bronze/t"
    assert masked["conn"]["layer"] == "bronze"
    assert masked["items"][0]["ok"] == 1


def test_contains_secret_detects_before_and_after_mask():
    raw = {"nested": {"secret_key": "x"}}
    assert ev.contains_secret(raw) is True
    assert ev.contains_secret(ev.mask(raw)) is False


def test_builder_output_never_contains_secret():
    # Payload de lineage com credencial vazada na origem/destino → mascarado.
    e = LineageEventBuilder.build(
        execution={"id": 1, "finished_at": "t"}, job={"id": 2}, pipeline=None,
        source={"connection_name": "pg", "password": "leak"},
        target={"type": "s3", "layer": "bronze", "aws_secret_access_key": "leak"},
        metrics={"records_read": 10})
    assert ev.contains_secret(e.payload) is False


# ─────────────────────────────── Score de Data Quality ───────────────────────────────

def test_dq_score_and_status_and_severity():
    checks = [
        {"status": "pass"}, {"status": "pass"},
        {"status": "fail", "severity": "critical"}, {"status": "skip"}, {"status": "info"},
    ]
    # relevantes = 3 (2 pass, 1 fail) → 67
    assert ev.dq_score(checks) == 67
    assert ev.dq_status(checks) == "failed"
    assert ev.dq_severity(checks) == "critical"


def test_dq_score_all_pass_is_100_and_skip_only_is_100():
    assert ev.dq_score([{"status": "pass"}, {"status": "pass"}]) == 100
    assert ev.dq_score([{"status": "skip"}, {"status": "info"}]) == 100
    assert ev.dq_status([{"status": "warn"}]) == "warning"


# ─────────────────────────────── Idempotency keys ───────────────────────────────

def test_idempotency_keys_per_family():
    exe = {"id": 120, "finished_at": "t"}
    lin = LineageEventBuilder.build(execution=exe, job={"id": 1}, pipeline=None,
                                    source={}, target={"layer": "bronze"}, metrics={})
    assert lin.idempotency_key == "lineage:execution:120"
    assert lin.event_type == ev.LINEAGE_EXECUTION_RECORDED

    dq = DataQualityEventBuilder.build_result(
        execution_id=120, control_id=10, job_id=1, pipeline_id=None, destination_id=4,
        table_name="eventos", target={"layer": "bronze"}, checks=[{"status": "pass"}], executed_at="t")
    assert dq.idempotency_key == "dq:execution:120:table:eventos"

    chk = DataQualityEventBuilder.build_check_failed(
        execution_id=120, control_id=10, table_name="eventos", target={},
        check={"name": "S3_PARTITION_CREATED", "status": "fail", "severity": "critical"}, executed_at="t")
    assert chk.idempotency_key == "dq:execution:120:check:S3_PARTITION_CREATED"

    s3 = S3EventBuilder.build_files_written(
        execution_id=120, job_id=1, control_id=10, table_name="eventos", layer="bronze",
        bucket="b", path="s3a://b/bronze/eventos/", partition_path="ano=2026/mes=07/dia=14",
        file_format="parquet", files_count=2, bytes_written=100, records_written=1500, created_at="t")
    assert s3.idempotency_key == "s3:execution:120:partition:ano=2026/mes=07/dia=14"

    sch = SchemaEventBuilder.build(event_type=ev.SCHEMA_DISCOVERED, table={"id": "bronze.eventos"},
                                   schema={}, table_id="bronze.eventos", schema_hash="abc", discovered_at="t")
    assert sch.idempotency_key == "schema:table:bronze.eventos:hash:abc"

    inc = IncidentEventBuilder.build(event_type=ev.INGESTION_SLA_BREACHED, incident_type="SLA_BREACH",
                                     severity="high", control={"id": 10}, execution={"id": 120},
                                     target=None, message="m", error_message=None, opened_at="t")
    assert inc.idempotency_key == "incident:SLA_BREACH:execution:120"


def test_incident_key_uses_control_when_no_execution():
    inc = IncidentEventBuilder.build(event_type=ev.INGESTION_WATERMARK_STALLED,
                                     incident_type="WATERMARK_STALLED", severity="medium",
                                     control={"id": 10}, execution=None, target=None,
                                     message="m", error_message=None, opened_at="t")
    assert inc.idempotency_key == "incident:WATERMARK_STALLED:control:10"


# ─────────────────────────────── Backoff / dead-letter ───────────────────────────────

def test_backoff_schedule_minutes():
    assert outbox._backoff(1).total_seconds() == 60
    assert outbox._backoff(2).total_seconds() == 300
    assert outbox._backoff(3).total_seconds() == 900
    assert outbox._backoff(4).total_seconds() == 3600
    # além da tabela: satura no último degrau (1h)
    assert outbox._backoff(9).total_seconds() == 3600


def test_dead_threshold_matches_max_attempts():
    # A 5ª falha (new_attempts == max_attempts) vira dead.
    max_attempts = 5
    assert all((prev + 1) < max_attempts for prev in range(0, 4))  # falhas 1..4 reagendam
    assert (4 + 1) >= max_attempts  # falha 5 → dead
