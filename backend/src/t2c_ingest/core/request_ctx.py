"""Per-request metadata (client IP, user-agent) exposed to non-request code via a ContextVar.

Set by an HTTP middleware; read by the audit writer so every audited action records who/where
without threading the Request through every service call. Empty in the worker/scheduler.
"""
from __future__ import annotations

import contextvars

_request_meta: contextvars.ContextVar[tuple[str | None, str | None]] = contextvars.ContextVar(
    "request_meta", default=(None, None)
)


def set_request_meta(ip: str | None, user_agent: str | None) -> None:
    _request_meta.set((ip, user_agent))


def get_request_meta() -> tuple[str | None, str | None]:
    return _request_meta.get()
