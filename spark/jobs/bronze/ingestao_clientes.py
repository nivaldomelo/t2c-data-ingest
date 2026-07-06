"""Example Spark bronze ingestion job.

Register as a job of type ``spark_python`` with script_path
``/opt/spark/jobs/bronze/ingestao_clientes.py`` and cluster "Spark Local Docker".
The worker submits it via ``spark-submit --master spark://spark-master:7077``.

This example reads a source table via JDBC and writes it to the bronze layer as Parquet.
Connection details are provided as env vars (job.env_vars) or spark-submit args so no secret
is baked into the script.
"""
from __future__ import annotations

import os

from pyspark.sql import SparkSession


def main() -> None:
    spark = (
        SparkSession.builder.appName("bronze.ingestao_clientes")
        .getOrCreate()
    )

    source_url = os.environ.get("SOURCE_JDBC_URL", "jdbc:postgresql://host.docker.internal:5432/source")
    source_table = os.environ.get("SOURCE_TABLE", "public.clientes")
    source_user = os.environ.get("SOURCE_USER", "postgres")
    source_password = os.environ.get("SOURCE_PASSWORD", "postgres")
    target_path = os.environ.get("BRONZE_PATH", "/data/bronze/clientes")

    print(f"[bronze.ingestao_clientes] reading {source_table} from {source_url}")
    df = (
        spark.read.format("jdbc")
        .option("url", source_url)
        .option("dbtable", source_table)
        .option("user", source_user)
        .option("password", source_password)
        .option("driver", "org.postgresql.Driver")
        .load()
    )

    count = df.count()
    print(f"[bronze.ingestao_clientes] read {count} rows; writing parquet to {target_path}")
    df.write.mode("overwrite").parquet(target_path)
    print("[bronze.ingestao_clientes] done")

    spark.stop()


if __name__ == "__main__":
    main()
