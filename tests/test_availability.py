from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from free_time.core.availability import calculate_availability
from free_time.core.periods import current_week_range, next_week_range
from free_time.models import TimeRange

JST = ZoneInfo("Asia/Tokyo")
MONDAY = date(2026, 9, 14)


def local_time(
    day_offset: int,
    hour: int,
    minute: int = 0,
    *,
    timezone_value=JST,
) -> datetime:
    current_date = MONDAY + timedelta(days=day_offset)
    return datetime.combine(
        current_date,
        time(hour, minute),
        tzinfo=timezone_value,
    )


def interval(
    day_offset: int,
    start_hour: int,
    end_hour: int,
    start_minute: int = 0,
    end_minute: int = 0,
) -> TimeRange:
    return TimeRange(
        local_time(day_offset, start_hour, start_minute),
        local_time(day_offset, end_hour, end_minute),
    )


def calculate(
    busy: tuple[TimeRange, ...] = (),
    *,
    workdays: tuple[int, ...] = (0,),
    week: TimeRange | None = None,
    now: datetime | None = None,
    workday_start: time = time(10, 0),
    workday_end: time = time(19, 0),
    min_slot_minutes: int = 30,
    slot_granularity_minutes: int = 30,
    timezone_value=JST,
):
    now = now or local_time(0, 9)
    week = week or current_week_range(now, timezone_value)
    return calculate_availability(
        week,
        busy,
        workdays=workdays,
        workday_start=workday_start,
        workday_end=workday_end,
        min_slot_minutes=min_slot_minutes,
        slot_granularity_minutes=slot_granularity_minutes,
        now=now,
        timezone=timezone_value,
    )


def slot_times(result) -> list[tuple[time, time]]:
    return [(slot.start.timetz(), slot.end.timetz()) for slot in result.slots]


def test_empty_calendar_returns_business_hours() -> None:
    result = calculate()

    assert slot_times(result) == [(time(10), time(19))]


@pytest.mark.parametrize(
    ("busy", "expected"),
    [
        ((interval(0, 12, 13),), [(time(10), time(12)), (time(13), time(19))]),
        ((interval(0, 9, 11),), [(time(11), time(19))]),
        ((interval(0, 18, 20),), [(time(10), time(18))]),
        ((interval(0, 9, 20),), []),
    ],
)
def test_busy_intervals_are_subtracted(
    busy: tuple[TimeRange, ...],
    expected: list[tuple[time, time]],
) -> None:
    assert slot_times(calculate(busy)) == expected


def test_overlapping_busy_intervals_are_merged() -> None:
    busy = (interval(0, 12, 14), interval(0, 13, 15))

    assert slot_times(calculate(busy)) == [(time(10), time(12)), (time(15), time(19))]


def test_adjacent_busy_intervals_are_merged() -> None:
    busy = (interval(0, 12, 13), interval(0, 13, 14))

    assert slot_times(calculate(busy)) == [(time(10), time(12)), (time(14), time(19))]


def test_grid_rounds_start_up_and_end_down() -> None:
    busy = (interval(0, 10, 14, end_minute=10), interval(0, 17, 19, start_minute=20))

    assert slot_times(calculate(busy)) == [(time(14, 30), time(17))]


def test_short_slots_are_discarded_but_exact_minimum_is_retained() -> None:
    short = calculate((interval(0, 9, 10), interval(0, 10, 19, start_minute=20)))
    exact = calculate((interval(0, 9, 10), interval(0, 10, 19, start_minute=30)))

    assert slot_times(short) == []
    assert slot_times(exact) == [(time(10), time(10, 30))]


def test_busy_outside_business_hours_does_not_change_availability() -> None:
    busy = (interval(0, 8, 9), interval(0, 19, 20))

    assert slot_times(calculate(busy)) == [(time(10), time(19))]


def test_cross_day_busy_interval_is_clipped_on_both_days() -> None:
    busy = (TimeRange(local_time(0, 18), local_time(1, 11)),)

    result = calculate(busy, workdays=(0, 1))

    assert slot_times(result) == [
        (time(10), time(18)),
        (time(11), time(19)),
    ]


def test_input_order_does_not_change_result() -> None:
    first = interval(0, 12, 14)
    second = interval(0, 13, 15)

    assert calculate((first, second)).slots == calculate((second, first)).slots


def test_busy_interval_in_another_timezone_is_compared_by_instant() -> None:
    busy_jst = interval(0, 12, 13)
    busy_utc = TimeRange(
        busy_jst.start.astimezone(timezone.utc),
        busy_jst.end.astimezone(timezone.utc),
    )

    assert calculate((busy_utc,)).slots == calculate((busy_jst,)).slots


def test_workdays_are_sorted_by_date_in_result() -> None:
    result = calculate(workdays=(4, 0, 2), now=local_time(0, 9))

    assert [day.date for day in result.days] == [
        date(2026, 9, 14),
        date(2026, 9, 16),
        date(2026, 9, 18),
    ]


def test_current_time_removes_past_days_and_rounds_today() -> None:
    now = local_time(3, 14, 12)

    result = calculate(workdays=(0, 1, 2, 3, 4), now=now)

    assert [(day.date, len(day.slots)) for day in result.days] == [
        (date(2026, 9, 14), 0),
        (date(2026, 9, 15), 0),
        (date(2026, 9, 16), 0),
        (date(2026, 9, 17), 1),
        (date(2026, 9, 18), 1),
    ]
    assert slot_times(result) == [
        (time(14, 30), time(19)),
        (time(10), time(19)),
    ]


def test_day_after_business_hours_has_no_candidates() -> None:
    result = calculate(now=local_time(0, 20))

    assert result.slots == ()


def test_next_week_is_not_clipped_by_current_time() -> None:
    now = local_time(3, 14, 12)
    next_week = next_week_range(now, JST)

    result = calculate(
        week=next_week,
        now=now,
        workdays=(0, 1, 2, 3, 4),
    )

    assert result.days[0].date == date(2026, 9, 21)
    assert result.days[0].slots[0].start.timetz() == time(10)


def test_naive_now_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate(now=datetime(2026, 9, 14, 9))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"min_slot_minutes": 0}, "positive integer"),
        ({"slot_granularity_minutes": 0}, "positive integer"),
        ({"workdays": ()}, "must not be empty"),
        ({"workday_start": time(19), "workday_end": time(10)}, "earlier"),
    ],
)
def test_invalid_policy_is_rejected(kwargs, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        calculate(**kwargs)
