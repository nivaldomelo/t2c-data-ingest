"""Validate the Spark 4 runtime end-to-end: versions on driver AND executors, library imports
distributed across the real workers, and that at least 3 distinct worker hosts participated.

Emits a machine-parseable line `RUNTIME_VALIDATION_JSON: {...}` and exits non-zero if fewer than
the required number of workers ran tasks or any required lib fails to import on an executor.
"""
import importlib
import json
import os
import socket
import sys

from pyspark.sql import SparkSession

REQUIRED_LIBS = ["pyspark", "pandas", "pyarrow", "numpy", "requests", "sqlalchemy", "pymysql", "psycopg"]
MIN_WORKERS = int(os.environ.get("VALIDATE_MIN_WORKERS", "3"))
PARTITIONS = int(os.environ.get("VALIDATE_PARTITIONS", "60"))


def check_partition(_):
    host = socket.gethostname()
    libs = {}
    for lib in REQUIRED_LIBS:
        try:
            mod = importlib.import_module(lib)
            libs[lib] = {"ok": True, "version": getattr(mod, "__version__", "unknown")}
        except Exception as exc:  # noqa: BLE001
            libs[lib] = {"ok": False, "error": str(exc)}
    return {"host": host, "python": sys.version.split()[0], "libs": libs}


def main() -> int:
    spark = SparkSession.builder.appName("validate_spark4_runtime").getOrCreate()
    sc = spark.sparkContext
    print(f"SPARK_VERSION={spark.version}")
    print(f"DRIVER_PYTHON={sys.version.split()[0]}")
    print(f"MASTER={sc.master}")

    results = sc.parallelize(range(PARTITIONS), PARTITIONS).map(check_partition).collect()

    hosts = {}
    lib_failures = []
    executor_python = set()
    for r in results:
        hosts[r["host"]] = hosts.get(r["host"], 0) + 1
        executor_python.add(r["python"])
        for lib, info in r["libs"].items():
            if not info["ok"]:
                lib_failures.append(f"{r['host']}:{lib}:{info.get('error')}")

    summary = {
        "spark_version": spark.version,
        "driver_python": sys.version.split()[0],
        "executor_python": sorted(executor_python),
        "workers_used": len(hosts),
        "hosts": hosts,
        "lib_failures": lib_failures[:20],
    }
    print("RUNTIME_VALIDATION_JSON: " + json.dumps(summary))
    spark.stop()

    if lib_failures:
        print(f"FALHA: bibliotecas não importaram em executores: {lib_failures[:5]}")
        return 2
    if len(hosts) < MIN_WORKERS:
        print(f"FALHA: execução usou {len(hosts)} worker(s), esperado >= {MIN_WORKERS}. Hosts: {hosts}")
        return 3
    print(f"OK: Spark {spark.version}, {len(hosts)} workers, libs OK em todos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
