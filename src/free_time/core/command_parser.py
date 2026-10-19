"""Deterministic parser for supported Slack availability commands."""

from __future__ import annotations

import re

from free_time.models import WEEK_MINUTES, Command, PeriodType

_PERIODS = {
    "今週": PeriodType.CURRENT_WEEK,
    "来週": PeriodType.NEXT_WEEK,
    "再来週": PeriodType.WEEK_AFTER_NEXT,
}
_STANDARD_COMMAND_PATTERN = re.compile(
    r"^(今週|来週|再来週)(?:の空き時間|の空き)?"
    r"(?:\s+([0-9]+)(?:分)?)?$"
)
_NATURAL_COMMAND_PATTERN = re.compile(
    r"^(今週|来週|再来週)の([0-9]+)分の空き(?:時間)?$"
)


def parse_command(text: str) -> Command | None:
    """Parse a supported command, returning None for unrelated input."""

    if not isinstance(text, str):
        return None

    normalized = text.strip()
    match = _STANDARD_COMMAND_PATTERN.fullmatch(normalized)
    if match is None:
        match = _NATURAL_COMMAND_PATTERN.fullmatch(normalized)
    if match is None:
        return None

    period = _PERIODS[match.group(1)]
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
