"""Register the local Spark cluster if it does not exist yet.

Idempotent — safe to run on every startup. Run after migrations:
    python scripts/seed_local_cluster.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from t2c_ingest.core.config import settings  # noqa: E402
from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.models.cluster import Cluster  # noqa: E402


def main() -> None:
    with SessionLocal() as db:
        existing = db.scalar(select(Cluster).where(Cluster.name == "Spark Local Docker"))
        if existing:
            print("Cluster 'Spark Local Docker' already exists — nothing to do.")
            return
        cluster = Cluster(
            name="Spark Local Docker",
            description="Local Spark cluster running in docker-compose (master + worker).",
            type="local_docker",
            spark_master_url=settings.spark_master_url,
            status="active",
            worker_count=1,
            total_cores=2,
            total_memory="2G",
            is_active=True,
            created_by="system",
        )
        db.add(cluster)
        db.commit()
        print(f"Registered cluster 'Spark Local Docker' -> {settings.spark_master_url}")


if __name__ == "__main__":
    main()
