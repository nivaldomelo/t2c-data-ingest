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
            changed = False
            if existing.expected_workers != settings.spark_expected_workers:
                existing.expected_workers = settings.spark_expected_workers
                changed = True
            if not existing.environment:
                existing.environment = "local"
                changed = True
            if not existing.runtime_image:
                existing.runtime_image = "t2c-data-ingest-spark-runtime:local"
                changed = True
            if changed:
                db.commit()
                print("Cluster 'Spark Local Docker' updated (expected_workers/environment/runtime_image).")
            else:
                print("Cluster 'Spark Local Docker' already up to date — nothing to do.")
            return
        cluster = Cluster(
            name="Spark Local Docker",
            description="Local Spark cluster running in docker-compose (master + 3 workers).",
            type="local_docker",
            spark_master_url=settings.spark_master_url,
            status="active",
            worker_count=3,
            total_cores=3,
            total_memory="3G",
            expected_workers=settings.spark_expected_workers,
            environment="local",
            runtime_image="t2c-data-ingest-spark-runtime:local",
            is_active=True,
            created_by="system",
        )
        db.add(cluster)
        db.commit()
        print(f"Registered cluster 'Spark Local Docker' -> {settings.spark_master_url}")


if __name__ == "__main__":
    main()
