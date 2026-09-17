from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from free_time.app import CALENDAR_ERROR_MESSAGE, FreeTimeApplication
from free_time.config import AppConfig
from free_time.models import TimeRange
from free_time.services.google_calendar import GoogleCalendarServiceError

TOKYO = ZoneInfo("Asia/Tokyo")


@dataclass
class FakeCalendar:
    busy: tuple[TimeRange, ...] = ()
    requested_periods: list[TimeRange] = field(default_factory=list)

    def get_busy_intervals(self, period: TimeRange) -> tuple[TimeRange, ...]:
        self.requested_periods.append(period)
        return self.busy


@dataclass
class FailingCalendar:
    requested_periods: list[TimeRange] = field(default_factory=list)

    def get_busy_intervals(self, period: TimeRange) -> tuple[TimeRange, ...]:
        self.requested_periods.append(period)
        raise GoogleCalendarServiceError("private credential detail")


def config(
    *,
    workdays: tuple[int, ...] = (0, 1, 2, 3, 4),
    workday_start: time = time(10, 0),
    workday_end: time = time(19, 0),
) -> AppConfig:
    return AppConfig(
        timezone=TOKYO,
        workday_start=workday_start,
        workday_end=workday_end,
        workdays=workdays,
        min_slot_minutes=30,
        slot_granularity_minutes=30,
        google_calendar_ids=("primary",),
        google_calendar_token_file=Path("calendar_token.json"),
        google_client_secret_file=Path("credentials.json"),
    )


def now() -> datetime:
    return datetime(2026, 9, 17, 14, 12, tzinfo=TOKYO)


def busy_on_thursday(start_hour: int, end_hour: int) -> TimeRange:
    return TimeRange(
        datetime(2026, 9, 17, start_hour, tzinfo=TOKYO),
        datetime(2026, 9, 17, end_hour, tzinfo=TOKYO),
    )


def test_unknown_command_returns_none_without_calling_calendar() -> None:
    calendar = FakeCalendar()
    application = FreeTimeApplication(config=config(), calendar=calendar)

    assert application.handle_command("こんにちは", now=now()) is None
    assert application.handle_command("今週は忙しい", now=now()) is None
    assert application.handle_command("", now=now()) is None
    assert calendar.requested_periods == []


def test_current_week_period_is_passed_to_calendar_once() -> None:
    calendar = FakeCalendar()
    application = FreeTimeApplication(config=config(), calendar=calendar)

    application.handle_command("今週", now=now())

    assert calendar.requested_periods == [
        TimeRange(
            datetime(2026, 9, 14, tzinfo=TOKYO),
            datetime(2026, 9, 21, tzinfo=TOKYO),
        )
    ]


def test_next_week_period_is_passed_to_calendar_once() -> None:
    calendar = FakeCalendar()
    application = FreeTimeApplication(config=config(), calendar=calendar)

    application.handle_command("来週", now=now())

    assert calendar.requested_periods == [
        TimeRange(
            datetime(2026, 9, 21, tzinfo=TOKYO),
            datetime(2026, 9, 28, tzinfo=TOKYO),
        )
    ]


def test_current_week_flow_uses_parser_availability_and_formatter() -> None:
    calendar = FakeCalendar(busy=(busy_on_thursday(15, 16),))
    application = FreeTimeApplication(config=config(), calendar=calendar)

    output = application.handle_command("今週", now=now())

    assert output is not None
    assert "📅 今週の空き時間" in output
    assert "・14:30〜15:00" in output
    assert "・16:00〜19:00" in output
    assert "・15:00〜16:00" not in output
    assert len(calendar.requested_periods) == 1


def test_full_business_window_returns_no_availability_message() -> None:
    calendar = FakeCalendar(busy=(busy_on_thursday(10, 19),))
    application = FreeTimeApplication(
        config=config(workdays=(3,)),
        calendar=calendar,
    )

    output = application.handle_command("今週", now=now())

    assert output == "📅 今週の空き時間\n\n条件に合う空き時間はありませんでした．"
    assert "📋 先方への送付用" not in output


def test_calendar_failure_returns_safe_fixed_message() -> None:
    calendar = FailingCalendar()
    application = FreeTimeApplication(config=config(), calendar=calendar)

    output = application.handle_command("今週", now=now())

    assert output == CALENDAR_ERROR_MESSAGE
    assert "private credential detail" not in output
    assert len(calendar.requested_periods) == 1


def test_custom_business_hours_are_honored() -> None:
    calendar = FakeCalendar()
    application = FreeTimeApplication(
        config=config(workday_start=time(9), workday_end=time(17)),
        calendar=calendar,
    )

    output = application.handle_command("来週", now=now())

    assert output is not None
    assert "・09:00〜17:00" in output


def test_custom_workdays_are_honored_in_application_flow() -> None:
    calendar = FakeCalendar()
    application = FreeTimeApplication(
        config=config(workdays=(0, 2, 4)),
        calendar=calendar,
    )

    output = application.handle_command("来週", now=now())

    assert output is not None
    assert "9/21（月）" in output
    assert "9/23（水）" in output
    assert "9/25（金）" in output
    assert "9/22（火）" not in output
    assert "9/24（木）" not in output


def test_naive_now_is_rejected() -> None:
    calendar = FakeCalendar()
    application = FreeTimeApplication(config=config(), calendar=calendar)

    with pytest.raises(ValueError, match="timezone-aware"):
        application.handle_command("今週", now=datetime(2026, 9, 17, 14, 12))

    assert calendar.requested_periods == []
