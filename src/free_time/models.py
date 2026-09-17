"""Small immutable domain models shared by later phases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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


__all__ = ["TimeRange"]
