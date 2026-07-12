"""Data Lake quick-query (baked system job).

Registra as tabelas do catálogo como temp views e executa um SELECT read-only já validado e
limitado pelo backend, emitindo o resultado em JSON no stdout.

Entradas:
  * env DATALAKE_VIEWS_JSON : JSON {view_name: s3a_path} (só views referenciadas são lidas)
  * env AWS_* / --conf spark.hadoop.fs.s3a.* : credenciais/endpoint (injetados pelo worker)
  * --sql   : SQL traduzido (schema__table) + LIMIT já aplicado pelo backend
  * --limit : teto de linhas coletadas

Saída (última linha): ``DATALAKE_QUERY_JSON: {status, columns, rows, rows_returned}``
"""
from __future__ import annotations

import argparse
import json
import os
import sys

MAX_ROWS_HARD = 1000


def _jsonable(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    try:
        import datetime
        if isinstance(v, (datetime.date, datetime.datetime)):
            return v.isoformat()
    except Exception:  # noqa: BLE001
        pass
    if isinstance(v, (bytes, bytearray)):
        return f"<{len(v)} bytes>"
    return str(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", required=True)
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()
    limit = max(1, min(args.limit, MAX_ROWS_HARD))
    sql = args.sql
    views = json.loads(os.environ.get("DATALAKE_VIEWS_JSON") or "{}")

    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("data-lake-query").getOrCreate()
    spark.conf.set("spark.sql.shuffle.partitions", "4")

    # Register ONLY the views referenced in the SQL (avoids reading every table's footer).
    lowered = sql.lower()
    registered = 0
    for name, path in views.items():
        if name.lower() in lowered:
            try:
                spark.read.parquet(path).createOrReplaceTempView(name)
                registered += 1
            except Exception:  # noqa: BLE001 - unreadable view; let the query fail naturally
                pass

    df = spark.sql(sql)
    columns = [{"name": f.name, "type": f.dataType.simpleString()} for f in df.schema.fields]
    collected = df.limit(limit).collect()
    rows = []
    for r in collected:
        d = r.asDict(recursive=True)
        rows.append({k: _jsonable(v) for k, v in d.items()})
    spark.stop()

    result = {"status": "success", "columns": columns, "rows": rows,
              "rows_returned": len(rows), "views_registered": registered}
    print("DATALAKE_QUERY_JSON: " + json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("DATALAKE_QUERY_JSON: " + json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)
