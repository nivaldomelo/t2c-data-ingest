"""Best-effort parsers that turn raw worker log lines into structured execution metadata.

The worker prints a few well-known lines (connection tests and an ``INGEST_SUMMARY`` line). These
parsers extract them so the UI can render structured cards. They are intentionally defensive:
truncated/incomplete lines must never raise — we return whatever could be parsed and the caller
keeps the full raw logs available.
"""
from __future__ import annotations

import re

# e.g. source-connection 'postgres_1' -> postgres host.docker.internal:5433/andromeda (ativa)
_CONN_RE = re.compile(
    r"(?P<role>source|target)-connection\s+'(?P<name>[^']+)'\s*->\s*"
    r"(?P<type>\w+)\s+(?P<host>[^:\s]+):(?P<port>\d+)/(?P<database>[^\s()]+)"
    r"(?:\s+\((?P<state>[^)]*)\))?",
    re.IGNORECASE,
)
# e.g. teste postgres_1: OK
_TEST_RE = re.compile(r"teste\s+(?P<name>[\w.-]+):\s*(?P<result>\S+)", re.IGNORECASE)

# Known keys of the INGEST_SUMMARY line, in emission order. Values may contain spaces
# (timestamps), so each value is captured lazily up to the next known key or end-of-line.
_SUMMARY_KEYS = ("table", "tipo", "incr_col", "watermark_anterior", "watermark_novo",
                 "lidos", "gravados", "status",
                 # S3 / Data Lake (pontos 14/15)
                 "target_type", "target_path", "file_format", "partition_columns",
                 "partition_path", "files_written", "bytes_written")
_KEY_ALT = "|".join(_SUMMARY_KEYS)
# Capture "<known_key>=<value>" where the value runs lazily until the next "<word>=" token
# (any key, including unknown extras like duracao_s) or end-of-line. This keeps values that
# contain spaces (timestamps) intact without letting trailing extra keys bleed in.
_SUMMARY_FIELD_RE = re.compile(
    rf"\b(?P<key>{_KEY_ALT})=(?P<val>.*?)(?=\s+\w+=|$)",
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if value == "" or value.lower() == "none":
        return None
    return value


def parse_connections(logs: str) -> tuple[dict | None, dict | None]:
    """Return (source, target) connection dicts parsed from the logs, or None each."""
    conns: dict[str, dict] = {}
    tests: dict[str, str] = {}
    for line in logs.splitlines():
        m = _CONN_RE.search(line)
        if m:
            role = m.group("role").lower()
            conns[role] = {
                "name": m.group("name"),
                "type": m.group("type").lower(),
                "host": m.group("host"),
                "port": int(m.group("port")),
                "database": m.group("database"),
                "test_status": None,
            }
            continue
        t = _TEST_RE.search(line)
        if t:
            tests[t.group("name")] = t.group("result")
    for c in conns.values():
        result = tests.get(c["name"])
        if result is not None:
            c["test_status"] = "success" if result.upper() in ("OK", "SUCESSO", "SUCCESS") else "failed"
    return conns.get("source"), conns.get("target")


def parse_ingest_summary(logs: str) -> dict | None:
    """Parse the last ``INGEST_SUMMARY`` line into a dict. Tolerant of truncation/missing keys."""
    summary_line = None
    for line in logs.splitlines():
        idx = line.find("INGEST_SUMMARY")
        if idx != -1:
            summary_line = line[idx + len("INGEST_SUMMARY"):].lstrip(": ").strip()
    if not summary_line:
        return None

    fields: dict[str, str | int | None] = {k: None for k in _SUMMARY_KEYS}
    found = False
    for m in _SUMMARY_FIELD_RE.finditer(summary_line):
        found = True
        fields[m.group("key")] = _clean(m.group("val"))
    if not found:
        return None

    for numeric in ("lidos", "gravados", "files_written", "bytes_written"):
        raw = fields.get(numeric)
        if raw is not None:
            try:
                fields[numeric] = int(str(raw).strip())
            except ValueError:
                pass  # leave the raw value if it's truncated / not an int
    return fields

