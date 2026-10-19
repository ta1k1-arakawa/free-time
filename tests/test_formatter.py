from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from free_time.core.formatter import format_availability
from free_time.models import (
    AvailabilityDay,
    AvailabilityResult,
    PeriodType,
    TimeRange,
)

JST = ZoneInfo("Asia/Tokyo")
WEEK = TimeRange(
    datetime(2026, 9, 14, tzinfo=JST),
    datetime(2026, 9, 21, tzinfo=JST),
)
EMPTY_MESSAGE = "条件に合う空き時間はありませんでした．"


def slot(day: date, start: time, end: time) -> TimeRange:
    return TimeRange(
        datetime.combine(day, start, tzinfo=JST),
        datetime.combine(day, end, tzinfo=JST),
    )


def result(*days: AvailabilityDay) -> AvailabilityResult:
    return AvailabilityResult(week=WEEK, days=days)


def test_formats_only_copy_ready_message_in_full() -> None:
    availability = result(
        AvailabilityDay(
            date(2026, 9, 17),
            (slot(date(2026, 9, 17), time(14, 30), time(19)),),
        ),
        AvailabilityDay(
            date(2026, 9, 18),
            (
                slot(date(2026, 9, 18), time(10), time(12)),
                slot(date(2026, 9, 18), time(15, 30), time(19)),
            ),
        ),
    )

    assert format_availability(availability, PeriodType.CURRENT_WEEK) == (
        "以下の日程で調整可能です．\n\n"
        "・9月17日（木）14:30〜19:00\n"
        "・9月18日（金）10:00〜12:00\n"
        "・9月18日（金）15:30〜19:00\n\n"
        "上記の中からご都合のよい時間帯をご指定いただけますと幸いです．"
    )


@pytest.mark.parametrize(
    "period",
    [PeriodType.CURRENT_WEEK, PeriodType.NEXT_WEEK, PeriodType.WEEK_AFTER_NEXT],
)
def test_same_copy_ready_format_for_each_week(period: PeriodType) -> None:
    availability = result(
        AvailabilityDay(
            date(2026, 9, 21),
            (slot(date(2026, 9, 21), time(10), time(19)),),
        ),
    )
    output = format_availability(availability, period)

    assert output == (
        "以下の日程で調整可能です．\n\n"
        "・9月21日（月）10:00〜19:00\n\n"
        "上記の中からご都合のよい時間帯をご指定いただけますと幸いです．"
    )
    assert "📅" not in output
    assert "📋" not in output


def test_duration_parameter_does_not_change_copy_ready_message() -> None:
    availability = result(
        AvailabilityDay(
            date(2026, 9, 17),
            (slot(date(2026, 9, 17), time(10), time(12)),),
        )
    )

    output = format_availability(
        availability,
        PeriodType.CURRENT_WEEK,
        duration_minutes=90,
    )

    assert "・9月17日（木）10:00〜12:00" in output
    assert "90分" not in output
    assert "今週" not in output


def test_no_slots_returns_only_empty_message() -> None:
    availability = result(AvailabilityDay(date(2026, 9, 17), ()))

    assert format_availability(availability, PeriodType.CURRENT_WEEK) == EMPTY_MESSAGE


def test_empty_day_is_skipped_when_another_day_has_slots() -> None:
    availability = result(
        AvailabilityDay(date(2026, 9, 17), ()),
        AvailabilityDay(
            date(2026, 9, 18),
            (slot(date(2026, 9, 18), time(10), time(10, 30)),),
        ),
    )

    output = format_availability(availability, PeriodType.CURRENT_WEEK)

    assert "9月17日" not in output
    assert "空き時間なし" not in output
    assert "・9月18日（金）10:00〜10:30" in output


def test_month_and_year_boundaries_use_date_derived_weekdays() -> None:
    availability = result(
        AvailabilityDay(
            date(2026, 9, 30),
            (slot(date(2026, 9, 30), time(10), time(11)),),
        ),
        AvailabilityDay(
            date(2026, 10, 1),
            (slot(date(2026, 10, 1), time(11), time(12)),),
        ),
        AvailabilityDay(
            date(2026, 12, 31),
            (slot(date(2026, 12, 31), time(13), time(14)),),
        ),
        AvailabilityDay(
            date(2027, 1, 1),
            (slot(date(2027, 1, 1), time(15), time(16)),),
        ),
    )

    output = format_availability(availability, PeriodType.CURRENT_WEEK)

    assert "・9月30日（水）10:00〜11:00" in output
    assert "・10月1日（木）11:00〜12:00" in output
    assert "・12月31日（木）13:00〜14:00" in output
    assert "・1月1日（金）15:00〜16:00" in output


def test_unknown_period_is_rejected() -> None:
    availability = result(
        AvailabilityDay(
            date(2026, 9, 17),
            (slot(date(2026, 9, 17), time(10), time(11)),),
        )
    )

    with pytest.raises(ValueError, match="Unsupported period"):
        format_availability(availability, "今週")  # type: ignore[arg-type]
