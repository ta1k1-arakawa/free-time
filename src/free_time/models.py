"""Small immutable domain models shared by later phases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


@dataclass(frozen=True, slots=True)
class TimeRange:
    """A non-empty timezone-aware interval.

    The interval is intentionally kept independent of calendar or Slack
    integrations so later domain code can use it with ordinary Python data.
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.start.utcoffset() is None:
            raise ValueError("TimeRange.start must be timezone-aware")
        if self.end.tzinfo is None or self.end.utcoffset() is None:
            raise ValueError("TimeRange.end must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("TimeRange.end must be later than start")


@dataclass(frozen=True, slots=True)
class AvailabilityDay:
    """Availability slots for one local calendar date."""

    date: date
    slots: tuple[TimeRange, ...]


@dataclass(frozen=True, slots=True)
class AvailabilityResult:
    """Availability grouped by date for a requested week."""

    week: TimeRange
    days: tuple[AvailabilityDay, ...]

    @property
    def slots(self) -> tuple[TimeRange, ...]:
        """Return all candidate slots in chronological day order."""

        return tuple(slot for day in self.days for slot in day.slots)


class PeriodType(Enum):
    """Supported relative periods for availability requests."""

    CURRENT_WEEK = "current_week"
    NEXT_WEEK = "next_week"


@dataclass(frozen=True, slots=True)
class Command:
    """A parsed availability command."""

    period: PeriodType


__all__ = [
    "AvailabilityDay",
    "AvailabilityResult",
    "Command",
    "PeriodType",
    "TimeRange",
]
