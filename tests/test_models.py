from __future__ import annotations

from datetime import datetime, timezone

import pytest

from free_time.models import Command, PeriodType, TimeRange


def test_time_range_is_immutable_and_timezone_aware() -> None:
    start = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 17, 11, 0, tzinfo=timezone.utc)
    time_range = TimeRange(start, end)

    assert time_range.start == start
    with pytest.raises((AttributeError, TypeError)):
        time_range.start = end  # type: ignore[misc]


def test_time_range_rejects_naive_or_empty_intervals() -> None:
    aware = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="timezone-aware"):
        TimeRange(datetime(2026, 9, 17, 10, 0), aware)
    with pytest.raises(ValueError, match="later"):
        TimeRange(aware, aware)


def test_command_duration_is_optional_and_immutable() -> None:
    without_duration = Command(PeriodType.CURRENT_WEEK)
    with_duration = Command(PeriodType.NEXT_WEEK, 60)

    assert without_duration.duration_minutes is None
    assert with_duration.duration_minutes == 60
