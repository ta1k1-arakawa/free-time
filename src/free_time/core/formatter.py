"""Deterministic Japanese text formatting for availability results."""

from __future__ import annotations

from datetime import date, datetime

from free_time.models import AvailabilityDay, AvailabilityResult, PeriodType, TimeRange

_WEEKDAY_LABELS = ("月", "火", "水", "木", "金", "土", "日")
_PERIOD_LABELS = {
    PeriodType.CURRENT_WEEK: "今週",
    PeriodType.NEXT_WEEK: "来週",
}


def format_availability(
    result: AvailabilityResult,
    period: PeriodType,
    *,
    duration_minutes: int | None = None,
) -> str:
    """Format an availability result for direct Slack posting."""

    period_label = _period_label(period)
    title = f"📅 {period_label}の空き時間"
    if duration_minutes is not None:
        title += f"（{duration_minutes}分以上）"
    if not result.slots:
        return f"{title}\n\n条件に合う空き時間はありませんでした．"

    day_blocks = [_format_day(day) for day in result.days]
    human_section = title + "\n\n" + "\n\n".join(day_blocks)
    share_section = _format_share_section(result)
    return f"{human_section}\n\n{share_section}"


def _format_day(day: AvailabilityDay) -> str:
    header = f"{day.date.month}/{day.date.day}（{_weekday_label(day.date)}）"
    if not day.slots:
        return f"{header}\n・空き時間なし"
    return "\n".join([header, *(_format_bullet(slot) for slot in day.slots)])


def _format_share_section(result: AvailabilityResult) -> str:
    lines = [
        "📋 先方への送付用",
        "",
        "以下の日程で調整可能です．",
        "",
    ]
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


def _format_bullet(slot: TimeRange) -> str:
    return f"・{_format_time(slot.start)}〜{_format_time(slot.end)}"


def _format_share_slot(day: date, slot: TimeRange) -> str:
    return (
        f"{day.month}月{day.day}日（{_weekday_label(day)}）"
        f"{_format_time(slot.start)}〜{_format_time(slot.end)}"
    )


def _format_time(value: datetime) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def _weekday_label(value: date) -> str:
    return _WEEKDAY_LABELS[value.weekday()]


def _period_label(period: PeriodType) -> str:
    try:
        return _PERIOD_LABELS[period]
    except KeyError as exc:
        raise ValueError(f"Unsupported period: {period!r}") from exc


__all__ = ["format_availability"]
