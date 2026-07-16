"""{{ job_name }} — {{ job_description }}

Job Spark DECLARATIVO e controlado pelo Controle de Ingestão do T2C Data Ingest.

Não recebe origem/destino por argumento. Recebe apenas o seletor do Controle
(--control-id | --control-name | --control-group). O worker resolve Controle + Origens +
Destinos e injeta (nunca em cmdline/log):
  * T2C_CONTROL_CONFIG      -> JSON (não-secreto) com origem + N destinos por papel/ordem
  * T2C_CONN_{id}_PASSWORD  -> senha de cada conexão de banco
  * AWS_* / spark.hadoop.fs.s3a.*  -> credenciais/endpoint do Data Lake
  * T2C_INGEST_DB_URL       -> base do ingest (p/ atualizar watermark/status no Controle)
  * T2C_EXECUTION_ID        -> id da execução (rastreabilidade no Data Lake)

Gerado a partir do template `spark_controlled_ingestion`. Ajuste apenas os pontos de
TRANSFORMAÇÃO (utils/transformations.py); leitura/escrita/segurança já seguem o padrão.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# Garante que a pasta do job esteja no path (spark-submit não a adiciona automaticamente).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.transformations import apply_transformations  # noqa: E402

# Metadados do job (preenchidos na criação; apenas informativos/rastreáveis).
JOB_NAME = "{{ job_name }}"
CONTROL_NAME = "{{ control_name }}"
CONTROL_GROUP = "{{ control_group }}"

MYSQL_DRIVER = "com.mysql.cj.jdbc.Driver"
PG_DRIVER = "org.postgresql.Driver"

log = logging.getLogger(JOB_NAME)


def parse_args():
    parser = argparse.ArgumentParser(description="{{ job_description }}")
    parser.add_argument("--control-id", required=False, default="{{ control_id }}")
    parser.add_argument("--control-name", required=False, default="{{ control_name }}")
    parser.add_argument("--control-group", required=False, default="{{ control_group }}")
    parser.add_argument("--execution-id", required=False)
    args, _ = parser.parse_known_args()
    return args


def create_spark_session():
    return SparkSession.builder.appName(JOB_NAME).getOrCreate()


def load_control_config(args):
    """Carrega a configuração declarativa injetada pelo worker (T2C_CONTROL_CONFIG).

    Estrutura: {"controls": [{nome_tabela, tipo_ingestao, source{...}, destinations[...]}, ...]}.
    As credenciais NÃO vêm aqui — a senha de cada conexão está em T2C_CONN_{id}_PASSWORD.
    """
    raw = os.environ.get("T2C_CONTROL_CONFIG")
    if not raw:
        raise RuntimeError("T2C_CONTROL_CONFIG ausente — o worker não resolveu a carga controlada.")
    controls = (json.loads(raw) or {}).get("controls", [])
    if not controls:
        raise RuntimeError("Nenhum controle na configuração injetada.")
    return controls


def _conn_password(conn_id) -> str:
    return os.environ.get(f"T2C_CONN_{conn_id}_PASSWORD", "")


def _jdbc_url(conn: dict) -> str:
    t = conn.get("type")
    if t == "mysql":
        return (f"jdbc:mysql://{conn['host']}:{conn['port']}/{conn['database']}"
                "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC")
    # stringtype=unspecified -> PG faz o cast implícito text->uuid/timestamp/numeric no staging.
    return f"jdbc:postgresql://{conn['host']}:{conn['port']}/{conn['database']}?stringtype=unspecified"


def read_source(spark, control: dict):
    """Lê a origem configurada no Controle, com filtro incremental por watermark quando aplicável."""
    source = control["source"]
    conn = source["conn"]
    table = f"{source['database']}.{source['table']}" if source.get("database") else source["table"]
    incremental_column = source.get("incremental_column")
    watermark = source.get("watermark")

    where = ""
    if control.get("tipo_ingestao") == "INCREMENTAL" and incremental_column and watermark:
        where = f" WHERE {incremental_column} > '{watermark}'"
    dbtable = f"(SELECT * FROM {table}{where}) AS t"
    log.info("Lendo origem %s.%s (incr=%s, %s)", conn.get("type"), table,
             incremental_column, "incremental" if where else "completa")

    driver = MYSQL_DRIVER if conn.get("type") == "mysql" else PG_DRIVER
    df = (spark.read.format("jdbc")
          .option("url", _jdbc_url(conn)).option("dbtable", dbtable)
          .option("user", conn["user"]).option("password", _conn_password(conn["id"]))
          .option("driver", driver).load())
    return df, incremental_column


def _dest(control: dict, role: str) -> dict | None:
    return next((d for d in control.get("destinations", []) if d.get("role") == role), None)


def write_datalake_copy(df, control: dict, execution_id: str) -> dict:
    """Escreve a cópia no Data Lake (papel datalake_copy), quando configurada."""
    datalake = _dest(control, "datalake_copy")
    if not datalake:
        log.info("Nenhum destino Data Lake configurado.")
        return {"enabled": False, "records_written": 0}

    now = datetime.now(timezone.utc)
    parts = datalake.get("partition_columns") or ["ano", "mes", "dia"]
    out = (df
           .withColumn("ano", F.lit(f"{now.year:04d}"))
           .withColumn("mes", F.lit(f"{now.month:02d}"))
           .withColumn("dia", F.lit(f"{now.day:02d}"))
           .withColumn("ingestion_timestamp", F.lit(now.isoformat()))
           .withColumn("ingestion_execution_id", F.lit(str(execution_id)))
           .withColumn("ingestion_source", F.lit(control["source"].get("source_type") or "")))

    path = (datalake.get("target_path") or "").rstrip("/")
    file_format = datalake.get("file_format") or "parquet"
    write_mode = datalake.get("write_mode") or "append"
    compression = datalake.get("compression") or "snappy"
    log.info("Gravando cópia Data Lake em %s (%s/%s, partição %s)", path, file_format, compression, parts)

    writer = df_writer = out.write.mode(write_mode).format(file_format)
    if file_format == "parquet" and compression:
        writer = writer.option("compression", compression)
    if parts:
        writer = writer.partitionBy(*parts)
    writer.save(path)
    return {"enabled": True, "target_path": path, "records_written": None, "partition_columns": parts}


def write_primary_destination(df, control: dict) -> dict:
    """Escreve no destino principal (papel primary)."""
    destination = _dest(control, "primary")
    if not destination:
        log.info("Nenhum destino principal configurado.")
        return {"records_written": 0}
    if destination["type"] == "postgres":
        return write_postgres(df, destination)
    raise ValueError(f"Destino principal não suportado neste template: {destination['type']}")


def _pg_columns(destination: dict):
    """(colunas de negócio sem id identity, colunas booleanas) da tabela final."""
    import psycopg
    conn = destination["conn"]
    with psycopg.connect(host=conn["host"], port=conn["port"], dbname=conn["database"],
                         user=conn["user"], password=_conn_password(conn["id"]), connect_timeout=15) as pg, \
            pg.cursor() as cur:
        cur.execute("""SELECT column_name, data_type, is_identity FROM information_schema.columns
                       WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position""",
                    (destination["target_schema"], destination["target_table"]))
        rows = cur.fetchall()
    business = [r[0] for r in rows if not (r[0] == "id" and r[2] == "YES")]
    booleans = [r[0] for r in rows if r[1] == "boolean"]
    return business, booleans


def write_postgres(df, destination: dict) -> dict:
    """PostgreSQL: append direto, ou staging + upsert (ON CONFLICT nas chaves) sem gravar id identity."""
    schema, table = destination["target_schema"], destination["target_table"]
    write_mode = destination.get("write_mode") or "append"
    conn = destination["conn"]
    final_fqn = f"{schema}.{table}"

    if write_mode != "upsert":
        (df.write.format("jdbc").mode(write_mode)
            .option("url", _jdbc_url(conn)).option("dbtable", final_fqn)
            .option("user", conn["user"]).option("password", _conn_password(conn["id"]))
            .option("driver", PG_DRIVER).save())
        return {"destination_type": "postgres", "target_table": final_fqn, "write_mode": write_mode}

    import psycopg
    stg_schema = destination.get("staging_schema") or schema
    stg_table = destination.get("staging_table") or f"stg_{table}_ingest"
    stg_fqn = f"{stg_schema}.{stg_table}"
    pk = destination.get("primary_key_columns") or []
    business, booleans = _pg_columns(destination)
    business = [c for c in business if c in df.columns]
    cols_csv = ", ".join(business)

    def _pg():
        return psycopg.connect(host=conn["host"], port=conn["port"], dbname=conn["database"],
                               user=conn["user"], password=_conn_password(conn["id"]), connect_timeout=15)

    with _pg() as c:
        c.autocommit = True
        with c.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {stg_fqn}")
            cur.execute(f"CREATE TABLE {stg_fqn} AS SELECT {cols_csv} FROM {final_fqn} WHERE 1=0")

    out = df.select(*business)
    for b in booleans:
        if b in out.columns:
            out = out.withColumn(b, F.col(b).cast("boolean"))
    (out.write.format("jdbc").mode("append")
        .option("url", _jdbc_url(conn)).option("dbtable", stg_fqn)
        .option("user", conn["user"]).option("password", _conn_password(conn["id"]))
        .option("driver", PG_DRIVER).save())

    non_pk = [c for c in business if c not in pk]
    set_clause = ", ".join(f"{c}=EXCLUDED.{c}" for c in non_pk) or (f"{pk[0]}={pk[0]}" if pk else "")
    on_conflict = f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {set_clause}" if pk else ""
    with _pg() as c:
        c.autocommit = True
        with c.cursor() as cur:
            cur.execute(f"INSERT INTO {final_fqn} ({cols_csv}) SELECT {cols_csv} FROM {stg_fqn} {on_conflict}")
            cur.execute(f"DROP TABLE IF EXISTS {stg_fqn}")
    log.info("PostgreSQL upsert -> %s (chave %s)", final_fqn, pk)
    return {"destination_type": "postgres", "target_table": final_fqn, "write_mode": "upsert",
            "staging_table": stg_fqn}


def update_watermark(control: dict, df, incremental_column):
    """Novo watermark = max(incremental_column) do lote. Só o worker/backend persiste no Controle."""
    if not incremental_column or incremental_column not in df.columns:
        return None
    row = df.agg(F.max(F.col(incremental_column)).alias("m")).collect()
    value = row[0]["m"] if row else None
    return None if value is None else str(value)


def process_control(spark, control: dict, execution_id: str):
    status = "SUCESSO"
    records_read = records_primary = records_datalake = 0
    new_watermark = None
    try:
        df, incremental_column = read_source(spark, control)
        df = df.cache()
        records_read = df.count()

        df = apply_transformations(df, control)

        datalake_result = write_datalake_copy(df, control, execution_id)
        write_primary_destination(df, control)

        records_primary = records_read
        records_datalake = records_read if datalake_result.get("enabled") else 0
        new_watermark = update_watermark(control, df, incremental_column) if records_read else None
    except Exception:
        status = "ERRO"
        raise
    finally:
        # Linha-máquina única consumida pelo worker (log_parser). Sem dados de negócio.
        print(
            "INGEST_SUMMARY: "
            f"job={JOB_NAME} table={control.get('nome_tabela')} tipo={control.get('tipo_ingestao')} "
            f"lidos={records_read} gravados_primary={records_primary} gravados_datalake={records_datalake} "
            f"watermark_novo={new_watermark} status={status}",
            flush=True,
        )
        try:
            df.unpersist()
        except Exception:
            pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    execution_id = args.execution_id or os.environ.get("T2C_EXECUTION_ID", "0")
    spark = create_spark_session()
    try:
        for control in load_control_config(args):
            process_control(spark, control, execution_id)
    except Exception:
        log.exception("Falha na execução do job %s", JOB_NAME)
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
