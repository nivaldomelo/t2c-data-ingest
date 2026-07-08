"""System job: prove that Spark tasks run distributed across multiple workers/executors.

Parallelizes many partitions, maps each to the executor hostname, and reports how many
partitions each distinct host processed. Fails if fewer than the expected number of workers
participated (e.g. everything ran on a single worker).

The worker parses the ``RUNTIME_VALIDATION_JSON:`` line to persist a structured result.
"""
from __future__ import annotations

import argparse
import json
import socket
import time
from collections import Counter

from pyspark.sql import SparkSession


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partitions", type=int, default=30)
    parser.add_argument("--expected-workers", type=int, default=3)
    args = parser.parse_args()

    spark = SparkSession.builder.appName("validate_distributed_execution").getOrCreate()
    sc = spark.sparkContext

    n = max(args.partitions, args.expected_workers)

    def where_am_i(_):
        # A little sleep spreads tasks so the scheduler uses all executors.
        time.sleep(0.2)
        return socket.gethostname()

    hosts = sc.parallelize(range(n), n).map(where_am_i).collect()
    by_host = dict(Counter(hosts))
    detected = len(by_host)
    ok = detected >= args.expected_workers

    print("Workers detectados:")
    for host, count in sorted(by_host.items()):
        print(f"  {host}: {count} partições")

    result = {
        "type": "distributed",
        "expected_workers": args.expected_workers,
        "detected_workers": detected,
        "partitions": n,
        "by_host": by_host,
        "status": "success" if ok else "failed",
    }
    print("RUNTIME_VALIDATION_JSON:" + json.dumps(result))
    if ok:
        print(f"Status: SUCESSO — execução distribuída validada em {detected} worker(s).")
    else:
        print(f"Status: ERRO — a execução usou apenas {detected} worker(s). Esperado pelo menos {args.expected_workers}.")

    spark.stop()
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
