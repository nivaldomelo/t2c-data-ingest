"""Spark job: copy software_test_lab.payments (MySQL) -> spark.payments (PostgreSQL).

Full upsert-by-id load (the source table has no ``updated_at``):
  1. Read the MySQL table via JDBC (selected columns only).
  2. Normalize types and validate enum values (invalid rows are dropped and reported).
  3. Land into a VARCHAR-typed staging table ``spark.stg_payments_ingest``.
  4. UPSERT staging -> ``spark.payments`` with explicit enum casts and ON CONFLICT (id).

SECURITY: credentials are NEVER hardcoded and NEVER logged. They are read from environment
variables that the T2C Data Ingest worker resolves from the registered connections
(``mysql_1`` / ``postgres_1``) and injects — see backend/scripts/run_worker.py. The
connection NAMES are passed as arguments (safe); the passwords only travel via env vars.

Env contract (set by the worker):
  SOURCE_HOST SOURCE_PORT SOURCE_DB SOURCE_USER SOURCE_PASSWORD   (MySQL)
  TARGET_HOST TARGET_PORT TARGET_DB TARGET_USER TARGET_PASSWORD   (PostgreSQL)
"""
from __future__ import annotations

import argparse
import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType, IntegerType, LongType, TimestampType

PAYMENT_METHODS = ["PIX", "CREDIT_CARD", "DEBIT_CARD", "BANK_SLIP", "CASH"]
PAYMENT_STATUSES = ["PENDING", "AUTHORIZED", "PAID", "FAILED", "REFUNDED", "CHARGEBACK"]

COLUMNS = [
    "id",
    "order_id",
    "payment_method",
    "provider_name",
    "transaction_code",
    "amount",
    "installment_count",
    "payment_status",
    "paid_at",
    "created_at",
]

# Simple types for the staging table (enums land as VARCHAR).
STAGING_DDL_COLUMNS = """
    id bigint,
    order_id bigint,
    payment_method varchar(40),
    provider_name varchar(80),
    transaction_code varchar(80),
    amount numeric(12,2),
    installment_count integer,
    payment_status varchar(40),
    paid_at timestamp,
    created_at timestamp
"""


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"[payments] variável de ambiente obrigatória ausente: {name}")
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--source-connection", required=False, help="Nome/ID da conexão de origem (informativo)")
    p.add_argument("--target-connection", required=False, help="Nome/ID da conexão de destino (informativo)")
    p.add_argument("--source-table", default="software_test_lab.payments")
    p.add_argument("--target-schema", default="spark")
    p.add_argument("--target-table", default="payments")
    p.add_argument("--staging-table", default="stg_payments_ingest")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    src_host = _require_env("SOURCE_HOST")
    src_port = os.environ.get("SOURCE_PORT", "3306")
    src_db = os.environ.get("SOURCE_DB") or args.source_table.split(".")[0]
    src_user = _require_env("SOURCE_USER")
    src_password = _require_env("SOURCE_PASSWORD")

    tgt_host = _require_env("TARGET_HOST")
    tgt_port = os.environ.get("TARGET_PORT", "5432")
    tgt_db = _require_env("TARGET_DB")
    tgt_user = _require_env("TARGET_USER")
    tgt_password = _require_env("TARGET_PASSWORD")

    target_schema = args.target_schema
    target_table = args.target_table
    staging_fqn = f"{target_schema}.{args.staging_table}"
    target_fqn = f"{target_schema}.{target_table}"
    # Source table name (strip the database qualifier for the JDBC dbtable if present).
    src_table = args.source_table.split(".")[-1]

    print(f"[payments] origem MySQL {src_host}:{src_port}/{src_db} tabela={src_table}")
    print(f"[payments] destino PostgreSQL {tgt_host}:{tgt_port}/{tgt_db} tabela={target_fqn}")

    spark = (
        SparkSession.builder.appName("mysql_to_postgres.payments")
        # Prefer IPv4 in the JVM (Docker bridge often has no IPv6 route).
        .config("spark.driver.extraJavaOptions", "-Djava.net.preferIPv4Stack=true")
        .config("spark.executor.extraJavaOptions", "-Djava.net.preferIPv4Stack=true")
        .getOrCreate()
    )

    mysql_url = f"jdbc:mysql://{src_host}:{src_port}/{src_db}?useSSL=false&allowPublicKeyRetrieval=true&zeroDateTimeBehavior=CONVERT_TO_NULL"
    pg_url = f"jdbc:postgresql://{tgt_host}:{tgt_port}/{tgt_db}"

    # 1) Read from MySQL (only the required columns).
    raw = (
        spark.read.format("jdbc")
        .option("url", mysql_url)
        .option("dbtable", src_table)
        .option("user", src_user)
        .option("password", src_password)
        .option("driver", "com.mysql.cj.jdbc.Driver")
        .load()
        .select(*COLUMNS)
    )

    # 2) Normalize types.
    df = (
        raw.withColumn("id", F.col("id").cast(LongType()))
        .withColumn("order_id", F.col("order_id").cast(LongType()))
        .withColumn("payment_method", F.col("payment_method").cast("string"))
        .withColumn("provider_name", F.col("provider_name").cast("string"))
        .withColumn("transaction_code", F.col("transaction_code").cast("string"))
        .withColumn("amount", F.col("amount").cast(DecimalType(12, 2)))
        .withColumn("installment_count", F.col("installment_count").cast(IntegerType()))
        .withColumn("payment_status", F.col("payment_status").cast("string"))
        .withColumn("paid_at", F.col("paid_at").cast(TimestampType()))
        .withColumn("created_at", F.col("created_at").cast(TimestampType()))
    )

    read_count = df.count()
    print(f"[payments] lidos do MySQL: {read_count}")

    # 3) Validate enum values; drop invalid rows and report how many.
    valid = df.filter(
        F.col("payment_method").isin(PAYMENT_METHODS)
        & F.col("payment_status").isin(PAYMENT_STATUSES)
    )
    valid_count = valid.count()
    invalid_count = read_count - valid_count
    if invalid_count:
        print(f"[payments] AVISO: {invalid_count} linha(s) com enum inválido foram descartadas.")

    # 4) Ensure schema + staging table exist and truncate staging (types under our control).
    _prepare_target(tgt_host, tgt_port, tgt_db, tgt_user, tgt_password, target_schema, staging_fqn)

    # 5) Write into staging via Spark JDBC (append into the pre-created VARCHAR-typed table).
    (
        valid.write.format("jdbc")
        .option("url", pg_url)
        .option("dbtable", staging_fqn)
        .option("user", tgt_user)
        .option("password", tgt_password)
        .option("driver", "org.postgresql.Driver")
        .option("batchsize", "1000")
        .mode("append")
        .save()
    )
    print(f"[payments] staging carregada: {valid_count} linha(s) em {staging_fqn}")

    # 6) UPSERT staging -> final with explicit enum casts.
    affected = _upsert(
        tgt_host, tgt_port, tgt_db, tgt_user, tgt_password, target_schema, target_table, args.staging_table
    )
    print(f"[payments] upsert em {target_fqn}: {affected} linha(s) inseridas/atualizadas")

    spark.stop()

    # Machine-readable summary captured by the worker into the execution history.
    print(f"INGEST_SUMMARY: read={read_count} valid={valid_count} invalid={invalid_count} upsert={affected}")
    return 0


def _pg_connect(host, port, db, user, password):
    """psycopg connection from the driver (worker container has psycopg installed)."""
    import psycopg

    return psycopg.connect(
        host=host, port=int(port), dbname=db, user=user, password=password, connect_timeout=10
    )


def _prepare_target(host, port, db, user, password, schema, staging_fqn) -> None:
    with _pg_connect(host, port, db, user, password) as conn:
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            cur.execute(f"CREATE TABLE IF NOT EXISTS {staging_fqn} ({STAGING_DDL_COLUMNS})")
            cur.execute(f"TRUNCATE {staging_fqn}")
        conn.commit()


def _upsert(host, port, db, user, password, schema, target_table, staging_table) -> int:
    target_fqn = f"{schema}.{target_table}"
    staging_fqn = f"{schema}.{staging_table}"
    method_enum = f"{schema}.payment_method_enum"
    status_enum = f"{schema}.payment_status_enum"
    sql = f"""
        INSERT INTO {target_fqn} (
            id, order_id, payment_method, provider_name, transaction_code,
            amount, installment_count, payment_status, paid_at, created_at
        )
        SELECT
            id, order_id, payment_method::{method_enum}, provider_name, transaction_code,
            amount, installment_count, payment_status::{status_enum}, paid_at, created_at
        FROM {staging_fqn}
        ON CONFLICT (id) DO UPDATE SET
            order_id = EXCLUDED.order_id,
            payment_method = EXCLUDED.payment_method,
            provider_name = EXCLUDED.provider_name,
            transaction_code = EXCLUDED.transaction_code,
            amount = EXCLUDED.amount,
            installment_count = EXCLUDED.installment_count,
            payment_status = EXCLUDED.payment_status,
            paid_at = EXCLUDED.paid_at,
            created_at = EXCLUDED.created_at
    """
    with _pg_connect(host, port, db, user, password) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            affected = cur.rowcount
        conn.commit()
    return affected


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        # Non-zero exit -> the worker marks the execution as failed and keeps the stack trace.
        sys.exit(1)
