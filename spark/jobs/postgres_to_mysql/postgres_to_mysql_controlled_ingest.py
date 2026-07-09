"""Control-table-driven Spark ingest: PostgreSQL -> MySQL.

Reads ingestion parameters from ``controle.t2c_data_controle_ingestao`` (which tables, tipo de
ingestão, coluna incremental, chave, watermark, status) and copies each active
POSTGRES->MYSQL table via JDBC, with FULL or INCREMENTAL load, staging + upsert
(INSERT ... ON DUPLICATE KEY UPDATE), and writes watermark/status/observacao back to control.

Nothing is hardcoded per run: pass ``--control-group`` (all tables of a group) or
``--table-name`` (single table).

SECURITY: credentials are never hardcoded/logged. The worker injects them as env vars:
  SOURCE_* (postgres_1)  TARGET_* (mysql_1)   — see backend/scripts/run_worker.py
The control DB is read via DATABASE_URL (the ingest DB), inherited from the worker env.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import BooleanType

# ── Destination DDLs (MySQL). Keyed by short table name. staging is created as LIKE final. ──
MYSQL_DDL = {
    "clientes": """
        CREATE TABLE IF NOT EXISTS {db}.clientes (
            id BIGINT NOT NULL PRIMARY KEY, cliente_uuid CHAR(36) NOT NULL,
            nome VARCHAR(150) NOT NULL, email VARCHAR(150) NOT NULL, documento VARCHAR(20),
            cidade VARCHAR(100), uf CHAR(2), ativo TINYINT(1) NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, origem_lote CHAR(36) NOT NULL,
            KEY idx_clientes_updated_at (updated_at), KEY idx_clientes_created_at (created_at)
        )""",
    "pedidos": """
        CREATE TABLE IF NOT EXISTS {db}.pedidos (
            id BIGINT NOT NULL PRIMARY KEY, pedido_uuid CHAR(36) NOT NULL, cliente_uuid CHAR(36) NOT NULL,
            numero_pedido VARCHAR(50) NOT NULL, status VARCHAR(30) NOT NULL, valor_total DECIMAL(14,2) NOT NULL,
            created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, origem_lote CHAR(36) NOT NULL,
            KEY idx_pedidos_updated_at (updated_at), KEY idx_pedidos_created_at (created_at)
        )""",
    "itens_pedido": """
        CREATE TABLE IF NOT EXISTS {db}.itens_pedido (
            id BIGINT NOT NULL PRIMARY KEY, item_uuid CHAR(36) NOT NULL, pedido_uuid CHAR(36) NOT NULL,
            sku VARCHAR(50) NOT NULL, produto VARCHAR(150) NOT NULL, quantidade INT NOT NULL,
            valor_unitario DECIMAL(14,2) NOT NULL, valor_total DECIMAL(14,2) NOT NULL,
            created_at DATETIME NOT NULL, origem_lote CHAR(36) NOT NULL,
            KEY idx_itens_pedido_created_at (created_at)
        )""",
    "pagamentos": """
        CREATE TABLE IF NOT EXISTS {db}.pagamentos (
            id BIGINT NOT NULL PRIMARY KEY, pagamento_uuid CHAR(36) NOT NULL, pedido_uuid CHAR(36) NOT NULL,
            metodo_pagamento VARCHAR(30) NOT NULL, status_pagamento VARCHAR(30) NOT NULL, valor DECIMAL(14,2) NOT NULL,
            created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, origem_lote CHAR(36) NOT NULL,
            KEY idx_pagamentos_updated_at (updated_at), KEY idx_pagamentos_created_at (created_at)
        )""",
    "eventos_status": """
        CREATE TABLE IF NOT EXISTS {db}.eventos_status (
            id BIGINT NOT NULL PRIMARY KEY, evento_uuid CHAR(36) NOT NULL, entidade VARCHAR(30) NOT NULL,
            entidade_uuid CHAR(36) NOT NULL, status_anterior VARCHAR(30), status_novo VARCHAR(30) NOT NULL,
            dt_evento DATETIME NOT NULL, origem_lote CHAR(36) NOT NULL,
            KEY idx_eventos_status_dt_evento (dt_evento)
        )""",
}


# ────────────────────────── infra helpers ──────────────────────────
def log(msg: str) -> None:
    print(f"[pg2mysql] {msg}", flush=True)


def _control_url() -> str:
    url = os.environ.get("CONTROL_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL (controle) não definido no ambiente.")
    return url.replace("postgresql+psycopg://", "postgresql://").replace("+psycopg", "")


def control_conn():
    import psycopg

    return psycopg.connect(_control_url(), connect_timeout=15)


def mysql_conn(db: str | None = None):
    import pymysql

    return pymysql.connect(
        host=os.environ["TARGET_HOST"],
        port=int(os.environ.get("TARGET_PORT") or 3306),
        user=os.environ["TARGET_USER"],
        password=os.environ["TARGET_PASSWORD"],
        database=db,
        connect_timeout=15,
        read_timeout=60,
        autocommit=True,
    )


def pg_jdbc_url() -> str:
    host = os.environ["SOURCE_HOST"]
    port = os.environ.get("SOURCE_PORT") or 5432
    db = os.environ["SOURCE_DB"]
    return f"jdbc:postgresql://{host}:{port}/{db}"


def mysql_jdbc_url(db: str) -> str:
    host = os.environ["TARGET_HOST"]
    port = os.environ.get("TARGET_PORT") or 3306
    return f"jdbc:mysql://{host}:{port}/{db}?useSSL=false&allowPublicKeyRetrieval=true&rewriteBatchedStatements=true"


# ────────────────────────── control-table access ──────────────────────────
CONTROL_COLS = [
    "id", "nome_tabela", "coluna_data", "coluna_ultima_alteracao", "grupo",
    "watermark_atual", "status", "tipo_ingestao", "colunas_chave", "origem", "destino", "ativo",
]


def load_control(group: str | None, table_name: str | None) -> list[dict]:
    where = ["ativo IS TRUE", "upper(origem) = 'POSTGRES'", "upper(destino) = 'MYSQL'"]
    params: list = []
    if table_name:
        where.append("nome_tabela = %s")
        params.append(table_name)
    if group:
        where.append("grupo = %s")
        params.append(group)
    sql = f"SELECT {', '.join(CONTROL_COLS)} FROM controle.t2c_data_controle_ingestao WHERE {' AND '.join(where)} ORDER BY nome_tabela"
    with control_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def update_control(control_id: int, **fields) -> None:
    fields["atualizado_em"] = datetime.now(timezone.utc).replace(tzinfo=None)
    sets = ", ".join(f"{k} = %s" for k in fields)
    with control_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE controle.t2c_data_controle_ingestao SET {sets} WHERE id = %s",
            [*fields.values(), control_id],
        )
        conn.commit()


# ────────────────────────── ingest logic ──────────────────────────
def incremental_column(rec: dict) -> str | None:
    return rec.get("coluna_ultima_alteracao") or rec.get("coluna_data")


def read_source(spark, schema_table: str, incr_col: str | None, watermark) -> "DataFrame":
    base = f"SELECT * FROM {schema_table}"
    if incr_col and watermark is not None:
        wm = watermark.isoformat(sep=" ") if isinstance(watermark, datetime) else str(watermark)
        base += f" WHERE {incr_col} > '{wm}'"
    dbtable = f"({base}) AS src"
    return (
        spark.read.format("jdbc")
        .option("url", pg_jdbc_url())
        .option("dbtable", dbtable)
        .option("user", os.environ["SOURCE_USER"])
        .option("password", os.environ["SOURCE_PASSWORD"])
        .option("driver", "org.postgresql.Driver")
        .option("fetchsize", "2000")
        .load()
    )


def normalize(df):
    """Booleans -> int (MySQL TINYINT); other types are JDBC-compatible as-is."""
    for field in df.schema.fields:
        if isinstance(field.dataType, BooleanType):
            df = df.withColumn(field.name, F.col(field.name).cast("int"))
    return df


def ensure_mysql(db: str, short: str, final_table: str, staging_table: str) -> None:
    ddl = MYSQL_DDL.get(short)
    with mysql_conn() as conn, conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}`")
        if ddl:
            cur.execute(ddl.format(db=f"`{db}`"))
        else:
            raise RuntimeError(f"Sem DDL MySQL para a tabela '{short}'.")
        # staging mirrors the final table structure.
        cur.execute(f"CREATE TABLE IF NOT EXISTS `{db}`.`{staging_table}` LIKE `{db}`.`{final_table}`")
        cur.execute(f"TRUNCATE TABLE `{db}`.`{staging_table}`")


def write_staging(df, db: str, staging_table: str) -> None:
    (
        df.write.format("jdbc")
        .option("url", mysql_jdbc_url(db))
        .option("dbtable", f"{db}.{staging_table}")
        .option("user", os.environ["TARGET_USER"])
        .option("password", os.environ["TARGET_PASSWORD"])
        .option("driver", "com.mysql.cj.jdbc.Driver")
        .option("batchsize", "1000")
        .mode("append")
        .save()
    )


def upsert(db: str, final_table: str, staging_table: str, columns: list[str], key: str) -> int:
    cols = ", ".join(f"`{c}`" for c in columns)
    updates = ", ".join(f"`{c}` = VALUES(`{c}`)" for c in columns if c != key)
    sql = (
        f"INSERT INTO `{db}`.`{final_table}` ({cols}) "
        f"SELECT {cols} FROM `{db}`.`{staging_table}` "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    with mysql_conn() as conn, conn.cursor() as cur:
        affected = cur.execute(sql)
        cur.execute(f"TRUNCATE TABLE `{db}`.`{staging_table}`")
    return affected


def process_table(spark, rec: dict) -> dict:
    nome = rec["nome_tabela"]
    db, short = nome.split(".", 1) if "." in nome else (os.environ.get("SOURCE_DB", ""), nome)
    final_table = short
    staging_table = f"stg_{short}_ingest"
    key = (rec.get("colunas_chave") or "id").split(",")[0].strip()
    tipo = (rec.get("tipo_ingestao") or "FULL").upper()
    incr_col = incremental_column(rec)
    watermark = rec.get("watermark_atual")
    started = time.monotonic()

    if tipo == "INCREMENTAL" and not incr_col:
        raise RuntimeError("INCREMENTAL sem coluna incremental (coluna_ultima_alteracao/coluna_data).")

    effective_wm = watermark if tipo == "INCREMENTAL" else None
    log(f"tabela={nome} tipo={tipo} incr_col={incr_col or '-'} watermark_anterior={watermark}")

    update_control(rec["id"], status="EM_EXECUCAO",
                   observacao=f"Ingestão iniciada em {datetime.now(timezone.utc).isoformat()}")

    df = normalize(read_source(spark, nome, incr_col if tipo == "INCREMENTAL" else None, effective_wm))
    columns = df.columns
    read_count = df.count()
    log(f"registros lidos: {read_count}")

    new_watermark = None
    if tipo == "INCREMENTAL" and incr_col and read_count > 0:
        mx = df.agg(F.max(F.col(incr_col)).alias("mx")).collect()[0]["mx"]
        new_watermark = mx

    ensure_mysql(db, short, final_table, staging_table)
    written = 0
    if read_count > 0:
        write_staging(df, db, staging_table)
        written = upsert(db, final_table, staging_table, columns, key)
    log(f"registros gravados (upsert afetados): {written}")

    duration = int(time.monotonic() - started)
    fields = {
        "status": "SUCESSO",
        "ultima_execucao": datetime.now(timezone.utc).replace(tzinfo=None),
        "observacao": f"Ingestão concluída com sucesso. Registros processados: {read_count}",
    }
    # Only advance watermark on success and when we actually saw new data.
    if new_watermark is not None:
        fields["watermark_atual"] = new_watermark
    update_control(rec["id"], **fields)

    print(
        f"INGEST_SUMMARY: table={nome} tipo={tipo} incr_col={incr_col or '-'} "
        f"watermark_anterior={watermark} watermark_novo={new_watermark} "
        f"lidos={read_count} gravados={written} status=SUCESSO duracao_s={duration}",
        flush=True,
    )
    return {"table": nome, "read": read_count, "written": written, "status": "SUCESSO"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--control-group")
    p.add_argument("--table-name")
    p.add_argument("--source-connection")  # informativo (worker injeta SOURCE_*)
    p.add_argument("--target-connection")  # informativo (worker injeta TARGET_*)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.control_group and not args.table_name:
        raise SystemExit("Informe --control-group ou --table-name.")

    records = load_control(args.control_group, args.table_name)
    if not records:
        log("Nenhum registro de controle ativo POSTGRES->MYSQL para os critérios informados.")
        return 0
    log(f"{len(records)} tabela(s) para processar: {[r['nome_tabela'] for r in records]}")

    spark = (
        SparkSession.builder.appName("postgres_to_mysql.controlled_ingest")
        .config("spark.driver.extraJavaOptions", "-Djava.net.preferIPv4Stack=true")
        .config("spark.executor.extraJavaOptions", "-Djava.net.preferIPv4Stack=true")
        .getOrCreate()
    )

    failures = 0
    try:
        for rec in records:
            try:
                process_table(spark, rec)
            except Exception as exc:  # noqa: BLE001 - isolate one table's failure
                failures += 1
                # Do NOT advance watermark on error; keep it as-is.
                short_msg = str(exc).splitlines()[0][:400]
                try:
                    update_control(rec["id"], status="ERRO", observacao=f"Falha: {short_msg}")
                except Exception:  # noqa: BLE001
                    pass
                log(f"ERRO em {rec['nome_tabela']}: {short_msg}")
                traceback.print_exc()  # full stack goes to the execution logs, not to observacao
    finally:
        spark.stop()

    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
