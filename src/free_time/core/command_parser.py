"""Deterministic parser for the small MVP command vocabulary."""

from __future__ import annotations

from free_time.models import Command, PeriodType

_COMMANDS = {
    "今週": PeriodType.CURRENT_WEEK,
    "今週の空き": PeriodType.CURRENT_WEEK,
    "今週の空き時間": PeriodType.CURRENT_WEEK,
    "来週": PeriodType.NEXT_WEEK,
    "来週の空き": PeriodType.NEXT_WEEK,
    "来週の空き時間": PeriodType.NEXT_WEEK,
}


def parse_command(text: str) -> Command | None:
    """Parse an allowed command, returning ``None`` for unknown input."""

    if not isinstance(text, str):
        return None
    period = _COMMANDS.get(text.strip())
    if period is None:
        return None
    return Command(period=period)


__all__ = ["parse_command"]
