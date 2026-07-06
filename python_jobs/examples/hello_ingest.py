"""Minimal pure-Python job example.

Register it as a job of type ``python`` with script_path
``/opt/t2c/python_jobs/examples/hello_ingest.py``. The worker runs it with ``python`` and
captures stdout/stderr into the execution logs.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone


def main() -> int:
    print(f"[hello_ingest] started at {datetime.now(timezone.utc).isoformat()}")
    print(f"[hello_ingest] argv: {sys.argv[1:]}")
    # Parameters passed via env by the worker (job.env_vars) are visible here.
    sample = os.environ.get("SAMPLE_PARAM", "<unset>")
    print(f"[hello_ingest] SAMPLE_PARAM={sample}")
    print("[hello_ingest] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
