"""Deterministic parser for the small MVP command vocabulary."""

from __future__ import annotations

import re

from free_time.models import WEEK_MINUTES, Command, PeriodType

_COMMANDS = {
    "今週": PeriodType.CURRENT_WEEK,
    "今週の空き": PeriodType.CURRENT_WEEK,
    "今週の空き時間": PeriodType.CURRENT_WEEK,
    "来週": PeriodType.NEXT_WEEK,
    "来週の空き": PeriodType.NEXT_WEEK,
    "来週の空き時間": PeriodType.NEXT_WEEK,
}
_COMMAND_PATTERN = re.compile(
    r"^(今週の空き時間|今週の空き|今週|来週の空き時間|来週の空き|来週)"
    r"(?:\s+([0-9]+))?$"
)


def parse_command(text: str) -> Command | None:
    """Parse an allowed command, returning ``None`` for unknown input."""

    if not isinstance(text, str):
        return None
    match = _COMMAND_PATTERN.fullmatch(text.strip())
    if match is None:
        return None
    period = _COMMANDS[match.group(1)]
    duration_text = match.group(2)
    if duration_text is None:
        return Command(period=period)
    try:
        duration_minutes = int(duration_text)
    except ValueError:
        return None
    if (
        duration_minutes <= 0
        or duration_minutes > WEEK_MINUTES
        or duration_minutes % 30 != 0
    ):
        return None
    return Command(period=period, duration_minutes=duration_minutes)


__all__ = ["parse_command"]
