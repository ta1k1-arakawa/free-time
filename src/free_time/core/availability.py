"""Pure availability calculation over timezone-aware time ranges."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Iterable

from free_time.models import AvailabilityDay, AvailabilityResult, TimeRange


def calculate_availability(
    week: TimeRange,
    busy_intervals: Iterable[TimeRange],
    *,
    workdays: Iterable[int],
    workday_start: time,
    workday_end: time,
    min_slot_minutes: int,
    slot_granularity_minutes: int,
    now: datetime,
    timezone: tzinfo,
) -> AvailabilityResult:
    """Calculate interview slots for the requested week.

    All inputs are domain values. Busy intervals are converted to the target
    timezone, clipped independently to each local business window, merged, and
    subtracted before current-time filtering and grid rounding are applied.
    """

    _validate_timezone(timezone)
    _validate_aware(now, "now")
    _validate_time(workday_start, "workday_start")
    _validate_time(workday_end, "workday_end")
    if workday_start >= workday_end:
        raise ValueError("workday_start must be earlier than workday_end")
    min_slot_minutes = _validate_positive_int(min_slot_minutes, "min_slot_minutes")
    slot_granularity_minutes = _validate_positive_int(
        slot_granularity_minutes,
        "slot_granularity_minutes",
    )
    weekdays = _validate_workdays(workdays)
    _validate_range(week, "week")

    local_now = now.astimezone(timezone)
    local_week_start = week.start.astimezone(timezone)
    local_week_end = week.end.astimezone(timezone)
    busy = tuple(_to_timezone(interval, timezone) for interval in busy_intervals)
    days: list[AvailabilityDay] = []

    current_date = local_week_start.date()
    while _local_midnight(current_date, timezone) < local_week_end:
        if current_date >= local_now.date() and current_date.weekday() in weekdays:
            slots = _calculate_day_slots(
                current_date=current_date,
                week_start=week.start,
                week_end=week.end,
                busy_intervals=busy,
                workday_start=workday_start,
                workday_end=workday_end,
                min_slot_minutes=min_slot_minutes,
                slot_granularity_minutes=slot_granularity_minutes,
                now=local_now,
                timezone=timezone,
            )
            days.append(AvailabilityDay(current_date, slots))
        current_date += timedelta(days=1)

    return AvailabilityResult(week=week, days=tuple(days))


def _calculate_day_slots(
    *,
    current_date: date,
    week_start: datetime,
    week_end: datetime,
    busy_intervals: tuple[TimeRange, ...],
    workday_start: time,
    workday_end: time,
    min_slot_minutes: int,
    slot_granularity_minutes: int,
    now: datetime,
    timezone: tzinfo,
) -> tuple[TimeRange, ...]:
    day_start = datetime.combine(current_date, workday_start, tzinfo=timezone)
    day_end = datetime.combine(current_date, workday_end, tzinfo=timezone)
    window_start = _later(day_start, week_start.astimezone(timezone))
    window_end = _earlier(day_end, week_end.astimezone(timezone))
    if not _before(window_start, window_end):
        return ()

    clipped_busy = _clip_busy_to_window(busy_intervals, window_start, window_end)
    merged_busy = _merge_intervals(clipped_busy)
    raw_free = _subtract_busy(window_start, window_end, merged_busy)

    candidates: list[TimeRange] = []
    day_midnight = _local_midnight(current_date, timezone)
    for free in raw_free:
        free_start = _later(free.start, now)
        if not _before(free_start, free.end):
            continue
        rounded_start = _ceil_to_grid(
            free_start,
            day_midnight,
            slot_granularity_minutes,
        )
        rounded_end = _floor_to_grid(
            free.end,
            day_midnight,
            slot_granularity_minutes,
        )
        if not _before(rounded_start, rounded_end):
            continue
        candidate = TimeRange(rounded_start, rounded_end)
        if candidate.end - candidate.start >= timedelta(minutes=min_slot_minutes):
            candidates.append(candidate)
    return tuple(candidates)


def _clip_busy_to_window(
    busy_intervals: tuple[TimeRange, ...],
    window_start: datetime,
    window_end: datetime,
) -> tuple[TimeRange, ...]:
    clipped: list[TimeRange] = []
    for interval in busy_intervals:
        start = _later(interval.start, window_start)
        end = _earlier(interval.end, window_end)
        if _before(start, end):
            clipped.append(TimeRange(start, end))
    return tuple(clipped)


def _merge_intervals(intervals: Iterable[TimeRange]) -> tuple[TimeRange, ...]:
    ordered = sorted(intervals, key=lambda value: _instant(value.start))
    if not ordered:
        return ()

    merged: list[TimeRange] = [ordered[0]]
    for interval in ordered[1:]:
        current = merged[-1]
        if _at_or_before(interval.start, current.end):
            if _before(current.end, interval.end):
                merged[-1] = TimeRange(current.start, interval.end)
        else:
            merged.append(interval)
    return tuple(merged)


def _subtract_busy(
    window_start: datetime,
    window_end: datetime,
    busy_intervals: Iterable[TimeRange],
) -> tuple[TimeRange, ...]:
    free: list[TimeRange] = []
    cursor = window_start
    for busy in busy_intervals:
        if _before(cursor, busy.start):
            free.append(TimeRange(cursor, busy.start))
        cursor = _later(cursor, busy.end)
    if _before(cursor, window_end):
        free.append(TimeRange(cursor, window_end))
    return tuple(free)


def _to_timezone(interval: TimeRange, target: tzinfo) -> TimeRange:
    _validate_range(interval, "busy interval")
    return TimeRange(
        interval.start.astimezone(target),
        interval.end.astimezone(target),
    )


def _ceil_to_grid(value: datetime, origin: datetime, minutes: int) -> datetime:
    grid = timedelta(minutes=minutes)
    elapsed = value - origin
    quotient, remainder = divmod(
        elapsed // timedelta(microseconds=1),
        grid // timedelta(microseconds=1),
    )
    if remainder:
        quotient += 1
    return origin + quotient * grid


def _floor_to_grid(value: datetime, origin: datetime, minutes: int) -> datetime:
    grid = timedelta(minutes=minutes)
    elapsed = value - origin
    quotient = elapsed // grid
    return origin + quotient * grid


def _local_midnight(current_date: date, timezone: tzinfo) -> datetime:
    return datetime.combine(current_date, time.min, tzinfo=timezone)


def _validate_range(value: TimeRange, name: str) -> None:
    if not isinstance(value, TimeRange):
        raise ValueError(f"{name} must be a TimeRange")


def _validate_time(value: time, name: str) -> None:
    if not isinstance(value, time) or value.tzinfo is not None:
        raise ValueError(f"{name} must be a naive local time")


def _validate_positive_int(value: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _validate_workdays(values: Iterable[int]) -> tuple[int, ...]:
    weekdays = tuple(values)
    if not weekdays:
        raise ValueError("workdays must not be empty")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 6
        for value in weekdays
    ):
        raise ValueError("workdays must contain integers from 0 to 6")
    if len(set(weekdays)) != len(weekdays):
        raise ValueError("workdays must not contain duplicates")
    return weekdays


def _validate_timezone(value: tzinfo | None) -> None:
    if not isinstance(value, tzinfo):
        raise ValueError("timezone must be a valid tzinfo instance")


def _validate_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _instant(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _before(left: datetime, right: datetime) -> bool:
    return _instant(left) < _instant(right)


def _at_or_before(left: datetime, right: datetime) -> bool:
    return _instant(left) <= _instant(right)


def _later(left: datetime, right: datetime) -> datetime:
    return left if not _before(left, right) else right


def _earlier(left: datetime, right: datetime) -> datetime:
    return left if not _before(right, left) else right


__all__ = ["calculate_availability"]
