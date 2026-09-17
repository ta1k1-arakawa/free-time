"""Calendar-independent week period calculations."""

from __future__ import annotations

from datetime import datetime, time, timedelta, tzinfo

from free_time.models import TimeRange


def week_range(
    now: datetime,
    timezone: tzinfo,
    week_offset: int = 0,
) -> TimeRange:
    """Return a local Monday-to-Monday half-open week range.

    ``now`` is converted to ``timezone`` before its local weekday is used.
    The returned boundaries are timezone-aware local midnights, so DST changes
    are handled by the supplied timezone implementation.
    """

    _validate_timezone(timezone)
    _validate_aware(now, "now")
    if not isinstance(week_offset, int):
        raise ValueError("week_offset must be an integer")

    local_now = now.astimezone(timezone)
    monday = local_now.date() - timedelta(days=local_now.weekday())
    monday += timedelta(days=7 * week_offset)
    start = datetime.combine(monday, time.min, tzinfo=timezone)
    end = datetime.combine(monday + timedelta(days=7), time.min, tzinfo=timezone)
    return TimeRange(start, end)


def current_week_range(now: datetime, timezone: tzinfo) -> TimeRange:
    """Return the week containing ``now`` in ``timezone``."""

    return week_range(now, timezone, week_offset=0)


def next_week_range(now: datetime, timezone: tzinfo) -> TimeRange:
    """Return the week immediately following the week containing ``now``."""

    return week_range(now, timezone, week_offset=1)


def _validate_timezone(value: tzinfo | None) -> None:
    if not isinstance(value, tzinfo):
        raise ValueError("timezone must be a valid tzinfo instance")


def _validate_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


__all__ = ["current_week_range", "next_week_range", "week_range"]
