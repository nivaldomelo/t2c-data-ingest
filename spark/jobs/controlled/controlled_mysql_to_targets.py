"""Job Spark genérico e DECLARATIVO: MySQL -> N destinos (PostgreSQL + cópia Data Lake S3).

Não recebe origem/destino por argumento. Recebe apenas o seletor do Controle de Ingestão
(--control-id | --control-name | --control-group). O worker resolve o Controle, as Origens e os
Destinos e injeta:
  * T2C_CONTROL_CONFIG  -> JSON (não-secreto) com origem + destinos por papel/ordem de cada controle
  * T2C_CONN_{id}_PASSWORD -> senha de cada conexão de banco (via env, nunca no cmdline/log)
  * AWS_* + spark.hadoop.fs.s3a.* (--conf) -> credenciais/endpoint do Data Lake
  * T2C_INGEST_DB_URL -> base do ingest (p/ escrever watermark/status no Controle)
  * T2C_EXECUTION_ID -> id da execução (rastreabilidade no Data Lake)

Para cada controle: lê o MySQL via JDBC com filtro incremental (watermark), normaliza tipos, grava
a cópia Bronze no S3 (Parquet particionado ano/mes/dia) e faz staging+upsert no PostgreSQL (sem
gravar o id identity), atualiza watermark/status e imprime INGEST_SUMMARY.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

MYSQL_DRIVER = "com.mysql.cj.jdbc.Driver"
PG_DRIVER = "org.postgresql.Driver"


def log(msg: str) -> None:
    print(f"[controlled_mysql_to_targets] {msg}", flush=True)


def _conn_password(conn_id: int) -> str:
    return os.environ.get(f"T2C_CONN_{conn_id}_PASSWORD", "")


def _mysql_url(c: dict) -> str:
    return f"jdbc:mysql://{c['host']}:{c['port']}/{c['database']}?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC"


def _pg_url(c: dict) -> str:
    # stringtype=unspecified -> PG faz o cast implícito text->uuid/timestamp/numeric no staging.
    return f"jdbc:postgresql://{c['host']}:{c['port']}/{c['database']}?stringtype=unspecified"


# ─────────────────────────────── Leitura MySQL (incremental) ───────────────────────────────

def read_source(spark, ctrl: dict):
    src = ctrl["source"]
    c = src["conn"]
    table = f"{src['database']}.{src['table']}"
    incr = src.get("incremental_column")
    wm = src.get("watermark")
    where = ""
    if incr and wm:
        where = f" WHERE {incr} > '{wm}'"
    dbtable = f"(SELECT * FROM {table}{where}) AS t"
    log(f"origem MySQL {table} incr={incr} watermark={wm} (carga {'incremental' if where else 'completa'})")
    df = (spark.read.format("jdbc")
          .option("url", _mysql_url(c)).option("dbtable", dbtable)
          .option("user", c["user"]).option("password", _conn_password(c["id"]))
          .option("driver", MYSQL_DRIVER).load())
    return df, incr


def _max_watermark(df, incr: str | None):
    if not incr or incr not in df.columns:
        return None
    row = df.agg(F.max(F.col(incr)).alias("m")).collect()
    v = row[0]["m"] if row else None
    return None if v is None else str(v)


# ─────────────────────────────── Escrita: cópia Data Lake S3 ───────────────────────────────

def write_s3(df, dest: dict, execution_id: str):
    now = datetime.now(timezone.utc)
    out = (df
           .withColumn("ano", F.lit(f"{now.year:04d}"))
           .withColumn("mes", F.lit(f"{now.month:02d}"))
           .withColumn("dia", F.lit(f"{now.day:02d}"))
           .withColumn("ingestion_timestamp", F.lit(now.isoformat()))
           .withColumn("ingestion_execution_id", F.lit(str(execution_id)))
           .withColumn("ingestion_source", F.lit("mysql")))
    path = (dest.get("target_path") or "").rstrip("/")
    parts = dest.get("partition_columns") or ["ano", "mes", "dia"]
    comp = dest.get("compression") or "snappy"
    log(f"S3 Bronze -> {path} (parquet/{comp}, partição {parts})")
    (out.write.mode(dest.get("write_mode") or "append")
        .partitionBy(*parts).option("compression", comp).parquet(path))
    return _s3_stats(dest, now)


def _s3_stats(dest: dict, when) -> dict:
    """Conta arquivos/bytes da partição recém-escrita via boto3 (barato, uma partição)."""
    try:
        import boto3
        from urllib.parse import urlparse
        p = urlparse((dest.get("target_path") or "").replace("s3a://", "s3://"))
        bucket = p.netloc
        base = p.path.strip("/")
        partition_path = f"ano={when.year:04d}/mes={when.month:02d}/dia={when.day:02d}"
        prefix = f"{base}/{partition_path}/"
        cfg = dest.get("conn") or {}
        kw = {}
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
        if region:
            kw["region_name"] = region
        if endpoint:
            kw["endpoint_url"] = endpoint
        cli = boto3.client("s3", **kw)
        files, size = 0, 0
        tok = None
        while True:
            resp = cli.list_objects_v2(Bucket=bucket, Prefix=prefix, **({"ContinuationToken": tok} if tok else {}))
            for o in resp.get("Contents", []):
                if o["Key"].endswith(".parquet"):
                    files += 1
                    size += int(o.get("Size", 0) or 0)
            if not resp.get("IsTruncated"):
                break
            tok = resp.get("NextContinuationToken")
        return {"files_written": files, "bytes_written": size, "partition_path": partition_path}
    except Exception as exc:  # noqa: BLE001
        log(f"aviso: não consegui contabilizar arquivos S3: {exc}")
        return {"files_written": None, "bytes_written": None,
                "partition_path": f"ano={when.year:04d}/mes={when.month:02d}/dia={when.day:02d}"}


# ─────────────────────────────── Escrita: PostgreSQL (staging + upsert) ───────────────────────────────

def _pg_conn(dest: dict):
    import psycopg
    c = dest["conn"]
    return psycopg.connect(host=c["host"], port=c["port"], dbname=c["database"],
                           user=c["user"], password=_conn_password(c["id"]), connect_timeout=15)


def _pg_target_columns(dest: dict) -> tuple[list[str], list[str]]:
    """(colunas de negócio sem id identity, colunas booleanas) da tabela final no PostgreSQL."""
    schema, table = dest["target_schema"], dest["target_table"]
    with _pg_conn(dest) as conn, conn.cursor() as cur:
        cur.execute("""SELECT column_name, data_type, is_identity FROM information_schema.columns
                       WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position""",
                    (schema, table))
        rows = cur.fetchall()
    business = [r[0] for r in rows if not (r[0] == "id" and r[2] == "YES")]
    booleans = [r[0] for r in rows if r[1] == "boolean"]
    return business, booleans


def write_postgres(df, dest: dict) -> int:
    schema, table = dest["target_schema"], dest["target_table"]
    stg_schema = dest.get("staging_schema") or schema
    stg_table = dest.get("staging_table") or f"stg_{table}_ingest"
    final_fqn = f"{schema}.{table}"
    stg_fqn = f"{stg_schema}.{stg_table}"
    pk = dest.get("primary_key_columns") or []
    business, booleans = _pg_target_columns(dest)
    business = [c for c in business if c in df.columns]  # só o que a origem trouxe

    # 1) staging com os MESMOS tipos da final (sem id/identity) e sem dados.
    cols_csv = ", ".join(business)
    with _pg_conn(dest) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {stg_fqn}")
            cur.execute(f"CREATE TABLE {stg_fqn} AS SELECT {cols_csv} FROM {final_fqn} WHERE 1=0")

    # 2) Spark grava no staging (append). Casts: booleanos (tinyint->boolean); demais via
    #    stringtype=unspecified no PG (uuid/timestamp/numeric).
    out = df.select(*business)
    for b in booleans:
        if b in out.columns:
            out = out.withColumn(b, F.col(b).cast("boolean"))
    c = dest["conn"]
    (out.write.format("jdbc").mode("append")
        .option("url", _pg_url(c)).option("dbtable", stg_fqn)
        .option("user", c["user"]).option("password", _conn_password(c["id"]))
        .option("driver", PG_DRIVER).save())

    # 3) upsert final <- staging (ON CONFLICT nas chaves UUID), sem gravar id.
    non_pk = [col for col in business if col not in pk]
    set_clause = ", ".join(f"{col}=EXCLUDED.{col}" for col in non_pk) or f"{pk[0]}={pk[0]}"
    conflict = ", ".join(pk) if pk else ""
    on_conflict = f"ON CONFLICT ({conflict}) DO UPDATE SET {set_clause}" if conflict else ""
    written = 0
    with _pg_conn(dest) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO {final_fqn} ({cols_csv}) SELECT {cols_csv} FROM {stg_fqn} {on_conflict}")
            cur.execute(f"SELECT count(*) FROM {stg_fqn}")
            written = cur.fetchone()[0]
            cur.execute(f"DROP TABLE IF EXISTS {stg_fqn}")
    log(f"PostgreSQL upsert -> {final_fqn} ({written} linhas, chave {pk})")
    return written


# ─────────────────────────────── Atualização do Controle ───────────────────────────────

def update_control(control_id: int, *, status: str, watermark: str | None) -> None:
    url = os.environ.get("T2C_INGEST_DB_URL")
    if not url:
        return
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=15) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                if watermark:
                    cur.execute("""UPDATE controle.t2c_data_controle_ingestao
                                   SET status=%s, ultima_execucao=now() AT TIME ZONE 'UTC',
                                       watermark_atual=%s, atualizado_em=now() AT TIME ZONE 'UTC'
                                   WHERE id=%s""", (status, watermark, control_id))
                else:
                    cur.execute("""UPDATE controle.t2c_data_controle_ingestao
                                   SET status=%s, ultima_execucao=now() AT TIME ZONE 'UTC',
                                       atualizado_em=now() AT TIME ZONE 'UTC'
                                   WHERE id=%s""", (status, control_id))
    except Exception as exc:  # noqa: BLE001
        log(f"aviso: não consegui atualizar o Controle #{control_id}: {exc}")


# ─────────────────────────────── Orquestração por controle ───────────────────────────────

def process_control(spark, ctrl: dict, execution_id: str) -> bool:
    name = ctrl["nome_tabela"]
    log(f"=== processando controle #{ctrl['control_id']} {name} ===")
    df, incr = read_source(spark, ctrl)
    df = df.cache()
    records_read = df.count()
    watermark_novo = _max_watermark(df, incr) if records_read else ctrl["source"].get("watermark")

    dests = sorted(ctrl["destinations"], key=lambda d: d.get("write_order", 1))
    gravados_pg, gravados_s3, s3_stats = 0, 0, {}
    try:
        for d in dests:
            if d["type"] == "s3":
                s3_stats = write_s3(df, d, execution_id)
                gravados_s3 = records_read
            elif d["type"] == "postgres":
                gravados_pg = write_postgres(df, d) if records_read else 0
        update_control(ctrl["control_id"], status="SUCESSO",
                       watermark=watermark_novo if records_read else None)
        _print_summary(ctrl, incr, records_read, gravados_pg, gravados_s3, s3_stats,
                       watermark_novo, "SUCESSO")
        return True
    except Exception as exc:  # noqa: BLE001 - falha não atualiza watermark
        update_control(ctrl["control_id"], status="ERRO", watermark=None)
        _print_summary(ctrl, incr, records_read, gravados_pg, gravados_s3, s3_stats,
                       ctrl["source"].get("watermark"), "ERRO", erro=str(exc))
        log(f"ERRO no controle {name}: {exc}")
        return False
    finally:
        df.unpersist()


def _print_summary(ctrl, incr, lidos, grav_pg, grav_s3, s3_stats, watermark_novo, status, erro=None):
    """Imprime o INGEST_SUMMARY.

    O worker (log_parser.parse_ingest_summary) lê os pares key=value que vêm APÓS o token
    ``INGEST_SUMMARY`` NA MESMA LINHA — por isso a linha-máquina é única. A regex ancora nas chaves
    conhecidas, então valores com espaço (watermark) são tolerados. Um bloco legível separado
    acompanha, para leitura humana (sem o token, para não confundir o parser)."""
    roles = {d["role"]: d["type"] for d in ctrl["destinations"]}
    s3_path = next((d.get("target_path") for d in ctrl["destinations"] if d["type"] == "s3"), "")
    gravados = grav_pg if grav_pg else grav_s3
    kv = {
        "table": ctrl["nome_tabela"], "tipo": ctrl.get("tipo_ingestao"), "incr_col": incr,
        "watermark_anterior": ctrl["source"].get("watermark"), "watermark_novo": watermark_novo,
        "lidos": lidos, "gravados": gravados, "status": status,
        "target_type": "s3", "target_path": s3_path, "file_format": "parquet",
        "partition_path": s3_stats.get("partition_path"),
        "files_written": s3_stats.get("files_written"), "bytes_written": s3_stats.get("bytes_written"),
    }
    # Linha-máquina única (consumida pelo worker/DQ/outbox).
    machine = "INGEST_SUMMARY: " + " ".join(f"{k}={v}" for k, v in kv.items() if v is not None)
    # Bloco legível (destinos/contagens por papel), sem o token INGEST_SUMMARY.
    readable = [
        "RESUMO_CARGA:",
        f"  origem={ctrl['source'].get('source_type')} destino_primary={roles.get('primary','')} "
        f"copia_datalake={roles.get('datalake_copy','')}",
        f"  gravados_postgres={grav_pg} gravados_s3={grav_s3}",
    ]
    if erro:
        readable.append(f"  erro={erro[:200]}")
    print("\n".join(readable), flush=True)
    print(machine, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-id")
    ap.add_argument("--control-name")
    ap.add_argument("--control-group")
    args, _ = ap.parse_known_args()

    raw = os.environ.get("T2C_CONTROL_CONFIG")
    if not raw:
        log("ERRO: T2C_CONTROL_CONFIG ausente — o worker não resolveu a carga controlada.")
        return 2
    config = json.loads(raw)
    controls = config.get("controls", [])
    if not controls:
        log("ERRO: nenhum controle na configuração.")
        return 2
    execution_id = os.environ.get("T2C_EXECUTION_ID", "0")

    spark = (SparkSession.builder
             .appName(f"controlled_mysql_to_targets[{args.control_name or args.control_group or args.control_id}]")
             .getOrCreate())
    ok_all = True
    try:
        for ctrl in controls:
            if not process_control(spark, ctrl, execution_id):
                ok_all = False
    finally:
        spark.stop()
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
