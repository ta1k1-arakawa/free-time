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


def slot(day: date, start: time, end: time) -> TimeRange:
    return TimeRange(
        datetime.combine(day, start, tzinfo=JST),
        datetime.combine(day, end, tzinfo=JST),
    )


def result(*days: AvailabilityDay) -> AvailabilityResult:
    return AvailabilityResult(week=WEEK, days=days)


def test_formats_human_and_share_sections_in_full() -> None:
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
        "📅 今週の空き時間\n\n"
        "9/17（木）\n"
        "・14:30〜19:00\n\n"
        "9/18（金）\n"
        "・10:00〜12:00\n"
        "・15:30〜19:00\n\n"
        "📋 先方への送付用\n\n"
        "以下の日程で調整可能です．\n\n"
        "・9月17日（木）14:30〜19:00\n"
        "・9月18日（金）10:00〜12:00\n"
        "・9月18日（金）15:30〜19:00\n\n"
        "上記の中からご都合のよい時間帯をご指定いただけますと幸いです．"
    )


def test_next_week_title_is_used() -> None:
    availability = result(
        AvailabilityDay(
            date(2026, 9, 21),
            (slot(date(2026, 9, 21), time(10), time(19)),),
        )
    )

    output = format_availability(availability, PeriodType.NEXT_WEEK)

    assert output.startswith("📅 来週の空き時間")


def test_no_slots_uses_empty_result_format_without_share_section() -> None:
    availability = result(AvailabilityDay(date(2026, 9, 17), ()))

    output = format_availability(availability, PeriodType.CURRENT_WEEK)

    assert output == "📅 今週の空き時間\n\n条件に合う空き時間はありませんでした．"
    assert "📋 先方への送付用" not in output


def test_day_without_slots_is_shown_when_another_day_has_slots() -> None:
    availability = result(
        AvailabilityDay(date(2026, 9, 17), ()),
        AvailabilityDay(
            date(2026, 9, 18),
            (slot(date(2026, 9, 18), time(10), time(10, 30)),),
        ),
    )

    output = format_availability(availability, PeriodType.CURRENT_WEEK)

    assert "9/17（木）\n・空き時間なし" in output
    assert "9/18（金）\n・10:00〜10:30" in output


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

    assert "9/30（水）" in output
    assert "・10月1日（木）11:00〜12:00" in output
    assert "12/31（木）" in output
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
