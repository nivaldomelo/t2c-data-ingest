"""Mask secrets in text before it is persisted to execution logs.

Job stdout/stderr is stored verbatim and readable by anyone with logs:read. A job that prints
a connection string, a DSN, an env dump or a traceback with credentials would leak them. This
redacts common credential shapes and any explicitly-known secret values (e.g. the decrypted
connection passwords injected into the job env).
"""
from __future__ import annotations

import re

_MASK = "***"

# key=value style: password=..., pwd=..., passwd=..., secret=..., token=..., api_key=...
_KV = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\b(\s*[=:]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s;,&]+)"
)
# credentials embedded in a URL/DSN: scheme://user:pass@host
_URL_CRED = re.compile(r"(?i)([a-z][a-z0-9+.\-]*://[^\s:/@]+:)([^\s@/]+)(@)")
# Authorization: Bearer <token> / Basic <token>
_AUTH = re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer|basic)\s+)(\S+)")
# AWS env vars and S3A hadoop confs. The generic _KV rule misses these: the leading '_' in
# AWS_ACCESS_KEY_ID defeats the \b, and s3a keys use '.' separators. Match the full key names.
_AWS_KV = re.compile(
    r"(?i)\b("
    r"aws_access_key_id|aws_secret_access_key|aws_session_token"
    r"|spark\.hadoop\.fs\.s3a\.(?:access\.key|secret\.key|session\.token)"
    r"|fs\.s3a\.(?:access\.key|secret\.key|session\.token)"
    r")(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s;,&]+)"
)


def mask_secrets(text: str | None, extra: list[str] | None = None) -> str:
    if not text:
        return text or ""
    out = text
    # Redact explicitly-known secret values first (exact substring match), longest first so a
    # value that is a prefix of another doesn't leave a tail exposed.
    for value in sorted({v for v in (extra or []) if v and len(v) >= 3}, key=len, reverse=True):
        out = out.replace(value, _MASK)
    out = _AWS_KV.sub(lambda m: f"{m.group(1)}{m.group(2)}{_MASK}", out)
    out = _KV.sub(lambda m: f"{m.group(1)}{m.group(2)}{_MASK}", out)
    out = _URL_CRED.sub(lambda m: f"{m.group(1)}{_MASK}{m.group(3)}", out)
    out = _AUTH.sub(lambda m: f"{m.group(1)}{_MASK}", out)
    return out
