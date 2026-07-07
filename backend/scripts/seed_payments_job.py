"""Seed the job definition ``mysql_payments_to_postgres_spark_payments`` (idempotent).

Creates/updates the Spark job that copies software_test_lab.payments (MySQL) into
spark.payments (PostgreSQL). The connections (``mysql_1`` / ``postgres_1``) are referenced by
name in the job arguments and resolved at run time by the worker — they must be registered in
the Conexões area first (the job can be seeded regardless).

Run:  python scripts/seed_payments_job.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.models.job import JobDefinition  # noqa: E402

NAME = "mysql_payments_to_postgres_spark_payments"
SCRIPT_PATH = "/opt/t2c/spark/jobs/mysql_to_postgres/payments_mysql_to_postgres.py"
DESCRIPTION = "Carga Spark da tabela software_test_lab.payments do MySQL para spark.payments no PostgreSQL"
ARGUMENTS = [
    "--source-connection", "mysql_1",
    "--target-connection", "postgres_1",
    "--source-table", "software_test_lab.payments",
    "--target-schema", "spark",
    "--target-table", "payments",
    "--staging-table", "stg_payments_ingest",
]


def main() -> None:
    with SessionLocal() as db:
        job = db.scalar(select(JobDefinition).where(JobDefinition.name == NAME))
        if job is None:
            job = JobDefinition(name=NAME, created_by="system")
            db.add(job)
        job.description = DESCRIPTION
        job.type = "spark_python"
        job.engine = "spark_cluster"
        job.script_path = SCRIPT_PATH
        job.arguments = ARGUMENTS
        job.is_active = True
        job.updated_by = "system"
        db.commit()
        print(f"Job '{NAME}' pronto (id={job.id}).")
        print("Lembre-se de cadastrar as conexões 'mysql_1' e 'postgres_1' em Conexões.")


if __name__ == "__main__":
    main()
