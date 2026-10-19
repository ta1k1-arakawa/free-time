"""Deterministic copy-ready Japanese formatting for availability results."""

from __future__ import annotations

from datetime import date, datetime

from free_time.models import AvailabilityResult, PeriodType, TimeRange

_WEEKDAY_LABELS = ("月", "火", "水", "木", "金", "土", "日")


def format_availability(
    result: AvailabilityResult,
    period: PeriodType,
    *,
    duration_minutes: int | None = None,
) -> str:
    """Return only the message suitable for forwarding to interviewers.

    Period and requested duration remain parameters for compatibility with
    existing callers; filtering is performed before formatting.
    """

    if not isinstance(period, PeriodType):
        raise ValueError(f"Unsupported period: {period!r}")
    if not result.slots:
        return "条件に合う空き時間はありませんでした．"

    lines = ["以下の日程で調整可能です．", ""]
    for day in result.days:
        for slot in day.slots:
            lines.append(f"・{_format_share_slot(day.date, slot)}")
    lines.extend(
        [
            "",
            "上記の中からご都合のよい時間帯をご指定いただけますと幸いです．",
        ]
    )
    return "\n".join(lines)


def _format_share_slot(day: date, slot: TimeRange) -> str:
    return (
        f"{day.month}月{day.day}日（{_weekday_label(day)}）"
        f"{_format_time(slot.start)}〜{_format_time(slot.end)}"
    )


def _format_time(value: datetime) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def _weekday_label(value: date) -> str:
    return _WEEKDAY_LABELS[value.weekday()]


__all__ = ["format_availability"]
