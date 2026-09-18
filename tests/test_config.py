from __future__ import annotations

from datetime import time
from pathlib import Path

import pytest

from free_time.config import ConfigError, load_config


def test_defaults_are_loaded_without_external_services() -> None:
    config = load_config(dotenv_path=Path("missing.env"), environ={})

    assert config.timezone.key == "Asia/Tokyo"
    assert config.workday_start == time(10, 0)
    assert config.workday_end == time(19, 0)
    assert config.workdays == (0, 1, 2, 3, 4)
    assert config.min_slot_minutes == 30
    assert config.slot_granularity_minutes == 30
    assert config.busy_buffer_minutes == 30
    assert config.google_calendar_ids == ("primary",)
    assert config.google_calendar_token_file == Path("calendar_token.json")
    assert config.log_level == "INFO"


def test_runtime_environment_overrides_dotenv(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "WORKDAY_START=08:00\nMIN_SLOT_MINUTES=60\nBUSY_BUFFER_MINUTES=30\n",
        encoding="utf-8",
    )

    config = load_config(
        dotenv_path,
        environ={"WORKDAY_START": "11:30", "BUSY_BUFFER_MINUTES": "0"},
    )

    assert config.workday_start == time(11, 30)
    assert config.min_slot_minutes == 60
    assert config.busy_buffer_minutes == 0


def test_dotenv_values_are_loaded(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "APP_TIMEZONE=UTC\nWORKDAYS=1,3,5\nLOG_LEVEL=debug\n",
        encoding="utf-8",
    )

    config = load_config(dotenv_path, environ={})

    assert config.timezone.key == "UTC"
    assert config.workdays == (1, 3, 5)
    assert config.log_level == "DEBUG"


def test_missing_runtime_values_raise_config_error() -> None:
    with pytest.raises(ConfigError, match="SLACK_BOT_TOKEN"):
        load_config(
            dotenv_path=Path("missing.env"),
            environ={},
            require_runtime=True,
        )


@pytest.mark.parametrize("value", ["", "abc", "0", "-1"])
def test_integer_settings_are_validated(value: str) -> None:
    with pytest.raises(ConfigError, match="MIN_SLOT_MINUTES"):
        load_config(
            dotenv_path=Path("missing.env"),
            environ={"MIN_SLOT_MINUTES": value},
        )


def test_invalid_time_is_rejected() -> None:
    with pytest.raises(ConfigError, match="WORKDAY_START"):
        load_config(
            dotenv_path=Path("missing.env"),
            environ={"WORKDAY_START": "25:00"},
        )


@pytest.mark.parametrize("value", ["7", "0,1,x", "0,1,1"])
def test_invalid_weekdays_are_rejected(value: str) -> None:
    with pytest.raises(ConfigError, match="WORKDAYS"):
        load_config(
            dotenv_path=Path("missing.env"),
            environ={"WORKDAYS": value},
        )


@pytest.mark.parametrize("value", ["-1", "abc", True])
def test_busy_buffer_requires_non_negative_integer(value) -> None:
    with pytest.raises(ConfigError, match="BUSY_BUFFER_MINUTES"):
        load_config(
            dotenv_path=Path("missing.env"),
            environ={"BUSY_BUFFER_MINUTES": value},
        )


def test_busy_buffer_rejects_value_beyond_supported_week_horizon() -> None:
    with pytest.raises(ConfigError, match="BUSY_BUFFER_MINUTES"):
        load_config(
            dotenv_path=Path("missing.env"),
            environ={"BUSY_BUFFER_MINUTES": "1000000000000"},
        )
