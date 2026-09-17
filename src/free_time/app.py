"""Application use case connecting the free-time domain components."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from free_time.config import AppConfig
from free_time.core.availability import calculate_availability
from free_time.core.command_parser import parse_command
from free_time.core.formatter import format_availability
from free_time.core.periods import current_week_range, next_week_range
from free_time.models import PeriodType, TimeRange
from free_time.services.google_calendar import GoogleCalendarServiceError

CALENDAR_ERROR_MESSAGE = (
    "Google Calendarから予定を取得できませんでした．時間をおいて再度お試しください．"
)


class CalendarBusyProvider(Protocol):
    """Small interface required by the application use case."""

    def get_busy_intervals(self, period: TimeRange) -> tuple[TimeRange, ...]:
        """Return busy intervals for one requested period."""

        ...


@dataclass(frozen=True, slots=True)
class FreeTimeApplication:
    """Handle one text command without owning external service lifecycles."""

    config: AppConfig
    calendar: CalendarBusyProvider

    def handle_command(self, text: str, *, now: datetime) -> str | None:
        """Return formatted availability, or ``None`` for an unknown command."""

        command = parse_command(text)
        if command is None:
            return None
        _validate_aware(now)

        period = _period_for_command(command.period, now, self.config)
        try:
            busy_intervals = self.calendar.get_busy_intervals(period)
        except GoogleCalendarServiceError:
            return CALENDAR_ERROR_MESSAGE

        availability = calculate_availability(
            period,
            busy_intervals,
            workdays=self.config.workdays,
            workday_start=self.config.workday_start,
            workday_end=self.config.workday_end,
            min_slot_minutes=self.config.min_slot_minutes,
            slot_granularity_minutes=self.config.slot_granularity_minutes,
            now=now,
            timezone=self.config.timezone,
        )
        return format_availability(availability, command.period)


def _period_for_command(
    period_type: PeriodType,
    now: datetime,
    config: AppConfig,
) -> TimeRange:
    if period_type is PeriodType.CURRENT_WEEK:
        return current_week_range(now, config.timezone)
    if period_type is PeriodType.NEXT_WEEK:
        return next_week_range(now, config.timezone)
    raise ValueError(f"Unsupported period: {period_type!r}")


def _validate_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be timezone-aware")


__all__ = [
    "CALENDAR_ERROR_MESSAGE",
    "CalendarBusyProvider",
    "FreeTimeApplication",
]
