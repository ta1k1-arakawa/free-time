"""Deterministic Japanese formatting for copy-ready Slack availability."""

from __future__ import annotations

from datetime import date, datetime

from free_time.models import AvailabilityResult, PeriodType, TimeRange

_WEEKDAY_LABELS = ("月", "火", "水", "木", "金", "土", "日")
_PERIOD_LABELS = {
    PeriodType.CURRENT_WEEK: "今週",
    PeriodType.NEXT_WEEK: "来週",
    PeriodType.WEEK_AFTER_NEXT: "再来週",
}

EMPTY_MESSAGE = "条件に合う空き時間はありませんでした．"


def format_availability(
    result: AvailabilityResult,
    period: PeriodType,
    *,
    duration_minutes: int | None = None,
) -> str:
    """Return only the availability slot lines, one per line.

    The reply intentionally carries no heading, introduction, or closing
    sentence: each line is ``・M月D日（曜）HH:MM〜HH:MM`` and nothing else.
    ``duration_minutes`` is accepted for interface compatibility and does
    not change the output. When there are no slots, only the empty-result
    message is returned.
    """

    try:
        _PERIOD_LABELS[period]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Unsupported period: {period!r}") from exc

    if not result.slots:
        return EMPTY_MESSAGE

    lines = [
        f"・{_format_share_slot(day.date, slot)}"
        for day in result.days
        for slot in day.slots
    ]
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


__all__ = ["EMPTY_MESSAGE", "format_availability"]
