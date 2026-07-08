"""System job: verify that the required Python libraries can be imported on EVERY worker.

Runs the import check on the executors (not just the driver), aggregating results per host so
a library missing on a single worker is caught. The worker parses ``RUNTIME_VALIDATION_JSON:``.
"""
from __future__ import annotations

import argparse
import importlib
import json
import socket

from pyspark.sql import SparkSession


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--libs", default="", help="Comma-separated import names to check")
    parser.add_argument("--partitions", type=int, default=30)
    parser.add_argument("--expected-workers", type=int, default=3)
    args = parser.parse_args()

    libs = [lib.strip() for lib in args.libs.split(",") if lib.strip()]

    spark = SparkSession.builder.appName("validate_runtime_libraries").getOrCreate()
    sc = spark.sparkContext
    n = max(args.partitions, args.expected_workers)

    def check_libs(_):
        host = socket.gethostname()
        out = {}
        for lib in libs:
            try:
                module = importlib.import_module(lib)
                out[lib] = {"ok": True, "version": getattr(module, "__version__", "unknown")}
            except Exception as exc:  # noqa: BLE001
                out[lib] = {"ok": False, "error": str(exc)[:200]}
        return (host, out)

    pairs = sc.parallelize(range(n), n).map(check_libs).collect()

    # Reduce to one entry per host.
    by_host: dict[str, dict] = {}
    for host, out in pairs:
        by_host.setdefault(host, out)

    failures = []
    for host, out in by_host.items():
        for lib, info in out.items():
            if not info.get("ok"):
                failures.append({"host": host, "lib": lib, "error": info.get("error")})

    ok = len(failures) == 0 and len(by_host) >= args.expected_workers and bool(libs)
    detected = len(by_host)

    print("Bibliotecas por worker:")
    for host, out in sorted(by_host.items()):
        summary = ", ".join(f"{lib}={'OK' if i.get('ok') else 'FALHOU'}" for lib, i in out.items())
        print(f"  {host}: {summary}")

    result = {
        "type": "libraries",
        "libs": libs,
        "expected_workers": args.expected_workers,
        "detected_workers": detected,
        "by_host": by_host,
        "failures": failures,
        "status": "success" if ok else "failed",
    }
    print("RUNTIME_VALIDATION_JSON:" + json.dumps(result))
    if ok:
        print(f"Status: SUCESSO — {len(libs)} biblioteca(s) disponível(is) em {detected} worker(s).")
    elif not libs:
        print("Status: ERRO — nenhuma biblioteca informada para validação.")
    else:
        for f in failures:
            print(f"  FALHA: {f['lib']} ausente em {f['host']}: {f['error']}")
        print(f"Status: ERRO — falhas de biblioteca detectadas ou workers insuficientes ({detected}).")

    spark.stop()
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
