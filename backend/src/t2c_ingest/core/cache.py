"""Tiny in-process TTL cache for expensive, shared, read-mostly computations.

Single-tenant tool: a process-local cache is enough to collapse many concurrent pollers into
one computation. Not a distributed cache — values live per API process and expire by TTL.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, TypeVar

_T = TypeVar("_T")
_store: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


def cached(key: str, ttl_seconds: float, producer: Callable[[], _T]) -> _T:
    now = time.monotonic()
    with _lock:
        hit = _store.get(key)
        if hit is not None and (now - hit[0]) < ttl_seconds:
            return hit[1]  # type: ignore[return-value]
    value = producer()  # produce outside the lock (may do I/O)
    with _lock:
        _store[key] = (now, value)
    return value


def invalidate(key: str | None = None) -> None:
    with _lock:
        if key is None:
            _store.clear()
        else:
            _store.pop(key, None)
