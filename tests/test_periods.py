from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from free_time.core.periods import current_week_range, next_week_range, week_range

JST = ZoneInfo("Asia/Tokyo")


def at_utc(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=JST)


def test_current_and_next_week_ranges() -> None:
    now = at_utc(2026, 9, 17, 12)

    current = current_week_range(now, JST)
    following = next_week_range(now, JST)

    assert current.start == at_utc(2026, 9, 14)
    assert current.end == at_utc(2026, 9, 21)
    assert following.start == at_utc(2026, 9, 21)
    assert following.end == at_utc(2026, 9, 28)


@pytest.mark.parametrize(
    ("now", "expected_start", "expected_end"),
    [
        (at_utc(2026, 9, 14, 8), at_utc(2026, 9, 14), at_utc(2026, 9, 21)),
        (at_utc(2026, 9, 20, 8), at_utc(2026, 9, 14), at_utc(2026, 9, 21)),
        (at_utc(2026, 9, 30, 8), at_utc(2026, 9, 28), at_utc(2026, 10, 5)),
        (at_utc(2026, 12, 31, 8), at_utc(2026, 12, 28), at_utc(2027, 1, 4)),
    ],
)
def test_week_boundaries_cover_month_and_year_changes(
    now: datetime,
    expected_start: datetime,
    expected_end: datetime,
) -> None:
    result = current_week_range(now, JST)

    assert result.start == expected_start
    assert result.end == expected_end


def test_week_offset_can_be_negative() -> None:
    now = at_utc(2026, 9, 17, 8)

    result = week_range(now, JST, week_offset=-1)

    assert result.start == at_utc(2026, 9, 7)
    assert result.end == at_utc(2026, 9, 14)


def test_naive_now_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        current_week_range(datetime(2026, 9, 17), JST)


def test_timezone_argument_requires_tzinfo() -> None:
    result = current_week_range(at_utc(2026, 9, 17), timezone.utc)
    assert result.start.tzinfo == timezone.utc

    with pytest.raises(ValueError, match="tzinfo"):
        current_week_range(at_utc(2026, 9, 17), None)  # type: ignore[arg-type]
