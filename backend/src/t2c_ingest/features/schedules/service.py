from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

DEFAULT_TZ = "America/Sao_Paulo"


class CronError(Exception):
    pass


def resolve_tz(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise CronError(f"Timezone inválida: {tz_name}")


def is_valid_cron(cron_expression: str | None) -> bool:
    if not cron_expression or not cron_expression.strip():
        return False
    return croniter.is_valid(cron_expression.strip())


def compute_next_run(
    cron_expression: str,
    tz_name: str | None,
    *,
    after: datetime | None = None,
    start_at: datetime | None = None,
) -> datetime:
    """Next fire time (tz-aware) strictly after ``after`` (default: now), never before start_at.

    croniter with a tz-aware base returns tz-aware datetimes in the same zone.
    """
    if not is_valid_cron(cron_expression):
        raise CronError("Expressão cron inválida.")
    tz = resolve_tz(tz_name)
    base = (after or datetime.now(timezone.utc)).astimezone(tz)
    # Never schedule before start_at.
    if start_at is not None:
        start_tz = start_at.astimezone(tz)
        if start_tz > base:
            base = start_tz
    itr = croniter(cron_expression.strip(), base)
    return itr.get_next(datetime)


def preview_next_runs(cron_expression: str, tz_name: str | None, count: int = 5) -> list[str]:
    """Return the next ``count`` fire times as ISO-8601 strings (with tz offset)."""
    tz = resolve_tz(tz_name)
    if not is_valid_cron(cron_expression):
        raise CronError("Expressão cron inválida.")
    base = datetime.now(timezone.utc).astimezone(tz)
    itr = croniter(cron_expression.strip(), base)
    out: list[str] = []
    for _ in range(max(1, min(count, 20))):
        out.append(itr.get_next(datetime).isoformat())
    return out
