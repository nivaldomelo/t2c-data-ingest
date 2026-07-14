# Eventos de integração com o t2c_data

O **T2C Data Ingest** executa as cargas e publica **tudo o que acontece operacionalmente** para o
`t2c_data`, que segue sendo a camada de catálogo, governança e metadados. A entrega usa o padrão
**outbox transacional** (`t2c_data_ingest.integration_outbox`): o produtor grava o evento na mesma
transação da sua escrita local; o worker entrega com **retry + backoff exponencial**, marca
`sent`/`dead` e alerta em falha persistente. Cada evento tem uma **idempotency_key**, então uma
reentrega nunca duplica no destino.

## Fluxo

```
Execução / DQ / Catálogo / Incidente
        ↓  (mesma transação)
integration_outbox (status=pending)
        ↓  worker publish_pending()
t2c_data.ingest_events        (sink genérico, SEMPRE — idempotente)
t2c_data.ingest_lineage       (lineage, compatibilidade)
        ↓
status=sent  |  falha → backoff → pending → … → dead (+ alerta)
```

Estados: `pending → processing → sent | failed → (backoff) pending → … → dead`.

Backoff por falha: **1min → 5min → 15min → 1h → dead** (`max_attempts` padrão = 5).

## Sink no t2c_data

Todos os eventos são gravados em `t2c_data.ingest_events`
(`event_type, aggregate_type, aggregate_id, idempotency_key (único), source, payload JSONB,
occurred_at, received_at`). Enquanto o `t2c_data` não tiver tabelas dedicadas, este sink é o
endpoint genérico de eventos; quando tiver, pode consumir daqui. O `lineage` também alimenta
`t2c_data.ingest_lineage` (consumidor atual).

Mapeamento sugerido para entidades dedicadas do t2c_data:

| event_type | tabela-alvo sugerida |
|---|---|
| `LINEAGE_EXECUTION_RECORDED` | `lineage_events` / `operational_lineage` |
| `DATA_QUALITY_RESULT_RECORDED` | `data_quality_results` / `quality_checks` |
| `SCHEMA_DISCOVERED` / `COLUMNS_DISCOVERED` | `catalog_columns` / `table_schema_versions` |
| `S3_FILES_WRITTEN` / `S3_PARTITION_CREATED` | `data_lake_assets` / `data_lake_partitions` / `data_lake_files` |
| `INGESTION_INCIDENT_OPENED` | `incidents` / `operational_incidents` |

## Camada (bronze/silver/gold)

A **camada** enviada é a camada **real** do destino, resolvida nesta ordem:

1. `destination.target_layer`
2. `ingestion_control.target_layer`
3. `ingestion_control.destino` (quando for `BRONZE`/`SILVER`/`GOLD`)
4. camada do catálogo de Data Lake (schema/layer)
5. primeiro segmento de camada no path S3 (`.../bronze/...`)
6. `null`

**Nunca** é o tipo da conexão (`s3`, `postgres`, `mysql`…). Ex.: `destination_type=s3` +
`target_layer=bronze` → `layer = "bronze"`.

## Segurança

Todo payload passa por `events.mask()` no enqueue e é remascarado ao ser exposto na API. Nenhum
segredo (senha, token, `aws_secret_access_key`, connection string…) vai para o payload, o log ou a
tela. Os endpoints de outbox exigem `ingest:integrations:read`; reprocessar exige
`ingest:integrations:retry`.

## Auditoria

Cada transição gera um `audit_events`: `T2C_DATA_OUTBOX_EVENT_SENT`, `…_FAILED`, `…_DEAD`,
`…_RETRIED`.

## Endpoints administrativos

```
GET  /api/v1/integrations/t2c-data/stats
GET  /api/v1/integrations/t2c-data/outbox?status=&event_type=&aggregate_type=&page=&page_size=
GET  /api/v1/integrations/t2c-data/outbox/{id}
POST /api/v1/integrations/t2c-data/outbox/{id}/retry
POST /api/v1/integrations/t2c-data/outbox/retry-dead
```

---

## Catálogo de eventos

Legenda: **quando** é gerado · **idempotency_key** · campos principais do payload.

### Lineage

#### `LINEAGE_EXECUTION_RECORDED`
- **Quando:** ao final de cada execução (via Data Quality).
- **idempotency_key:** `lineage:execution:{execution_id}`
- **Payload:**
```json
{
  "event_type": "LINEAGE_EXECUTION_RECORDED",
  "execution": {"id":120,"status":"success","started_at":"…","finished_at":"…","duration_seconds":130},
  "job": {"id":15,"name":"postgres_to_s3_eventos_status"},
  "pipeline": {"id":3},
  "source": {"connection_id":1,"connection_name":"postgres_1","type":"postgres","database":"andromeda","schema":"massa_teste","table":"eventos_status"},
  "target": {"destination_id":4,"connection_id":10,"connection_name":"Datalake-Via-Lactea","type":"s3","bucket":"datalake-t2c-data-integracao","path":"s3a://datalake-t2c-data-integracao/bronze/eventos_status/","layer":"bronze","file_format":"parquet","partition_columns":["ano","mes","dia"]},
  "metrics": {"records_read":1500,"records_written":1500,"files_written":2,"bytes_written":593200}
}
```

### Data Quality

- `DATA_QUALITY_RESULT_RECORDED` — `dq:execution:{execution_id}:table:{table}` — resultado completo (status, score, severity, checks).
- `DATA_QUALITY_SCORE_UPDATED` — `dq_score:execution:{execution_id}:table:{table}` — score + status.
- `DATA_QUALITY_CHECK_FAILED` — `dq:execution:{execution_id}:check:{check_name}` — um por check crítico que falhou.

```json
{
  "event_type": "DATA_QUALITY_RESULT_RECORDED",
  "execution_id": 120, "control_id": 10, "job_id": 15, "destination_id": 4,
  "table_name": "eventos_status",
  "target": {"type":"s3","layer":"bronze","bucket":"…","path":"s3a://…/bronze/eventos_status/","file_format":"parquet"},
  "quality": {"status":"success","score":100,"severity":"low","checks":[{"name":"S3_PARTITION_CREATED","status":"pass","severity":"critical","message":"…"}]},
  "executed_at": "2026-07-14T10:02:10"
}
```

### Schema / colunas

- `SCHEMA_DISCOVERED` / `COLUMNS_DISCOVERED` — `schema:table:{layer.table}:hash:{schema_hash}` — no scan do Data Lake Catalog.
- `SCHEMA_CHANGED` — mesma chave com hash novo — quando o hash do schema muda entre scans.

```json
{
  "event_type": "SCHEMA_DISCOVERED",
  "table": {"name":"eventos_status","full_name":"bronze.eventos_status","layer":"bronze","type":"s3","bucket":"…","path":"s3a://…/bronze/eventos_status/","file_format":"parquet"},
  "schema": {"schema_hash":"abc123","columns_count":11,"partition_columns":["ano","mes","dia"],"columns":[{"name":"evento_uuid","type":"string","nullable":false,"is_partition":false},{"name":"ano","type":"string","nullable":true,"is_partition":true}]},
  "discovered_at": "2026-07-14T10:05:00"
}
```

### Data Lake / S3

- `S3_FILES_WRITTEN` — `s3:execution:{execution_id}:partition:{partition_path|root}`.
- `S3_PARTITION_CREATED` — `s3_part:execution:{execution_id}:partition:{partition_path|root}`.

```json
{
  "event_type": "S3_FILES_WRITTEN",
  "execution_id":120,"job_id":15,"control_id":10,"table_name":"eventos_status","layer":"bronze",
  "bucket":"datalake-t2c-data-integracao","path":"s3a://…/bronze/eventos_status/",
  "partition_path":"ano=2026/mes=07/dia=14","file_format":"parquet",
  "files_count":2,"bytes_written":593200,"records_written":1500,"created_at":"2026-07-14T10:02:10"
}
```

### Incidentes operacionais

- `INGESTION_INCIDENT_OPENED` / `INGESTION_INCIDENT_RESOLVED` — `incident:{type}:execution:{id}` (ou `:control:{id}`).
- `INGESTION_SLA_BREACHED` — SLA excedido.
- `INGESTION_ZERO_RECORDS_DETECTED` — carga concluiu com zero registros (atenção/crítico).
- `INGESTION_WATERMARK_STALLED` — watermark não avançou.

Gerados: falha crítica de DQ (na avaliação) e SLA/zero registros/watermark (monitor a cada tick do
worker, idempotente pela chave — não gera duplicado enquanto a condição persistir).

```json
{
  "event_type": "INGESTION_INCIDENT_OPENED",
  "incident": {"type":"SLA_BREACH","severity":"high","message":"Carga … excedeu o SLA de 60min.","error_message":null},
  "control": {"id":10,"name":"massa_teste.eventos_status","owner_name":"Engenharia de Dados","criticality":"alta"},
  "execution": {"id":120,"status":"success","duration_seconds":4900},
  "target": {"destination_id":4,"type":"s3","layer":"bronze","path":"s3a://…/bronze/eventos_status/"},
  "opened_at": "2026-07-14T10:10:00"
}
```
