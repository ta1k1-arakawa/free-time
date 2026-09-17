from __future__ import annotations

import pytest

from free_time.core.command_parser import parse_command
from free_time.models import Command, PeriodType


@pytest.mark.parametrize(
    "text",
    ["今週", " 今週", "今週 ", "今週の空き", "今週の空き時間"],
)
def test_current_week_phrases_parse_to_current_week(text: str) -> None:
    assert parse_command(text) == Command(PeriodType.CURRENT_WEEK)


@pytest.mark.parametrize(
    "text",
    ["来週", " 来週", "来週 ", "来週の空き", "来週の空き時間"],
)
def test_next_week_phrases_parse_to_next_week(text: str) -> None:
    assert parse_command(text) == Command(PeriodType.NEXT_WEEK)


@pytest.mark.parametrize(
    "text",
    [
        "こんにちは",
        "今週は忙しい",
        "今週は忙しいですね",
        "空いてる？",
        "今日",
        "明日",
        "今月",
        "再来週",
        "今週お願いします",
        "来週面接",
        "今週の予定",
        "",
        "   ",
    ],
)
def test_unknown_phrases_do_not_parse(text: str) -> None:
    assert parse_command(text) is None


def test_parser_only_trims_outer_whitespace() -> None:
    assert parse_command("\n来週の空き時間\n") == Command(PeriodType.NEXT_WEEK)
    assert parse_command("今 週") is None
