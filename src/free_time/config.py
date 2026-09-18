"""Environment-based application configuration."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values

from free_time.models import WEEK_MINUTES


class ConfigError(ValueError):
    """Raised when application configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Validated application settings.

    Secrets are excluded from the dataclass representation so that accidental
    logging of an ``AppConfig`` instance does not expose them.
    """

    timezone: ZoneInfo
    workday_start: time
    workday_end: time
    workdays: tuple[int, ...]
    min_slot_minutes: int
    slot_granularity_minutes: int
    google_calendar_ids: tuple[str, ...]
    google_calendar_token_file: Path
    google_client_secret_file: Path
    google_calendar_token_json: str | None = field(default=None, repr=False)
    slack_bot_token: str | None = field(default=None, repr=False)
    slack_signing_secret: str | None = field(default=None, repr=False)
    slack_allowed_channel_id: str | None = None
    log_level: str = "INFO"
    busy_buffer_minutes: int = 30

    def validate_runtime(self) -> None:
        """Validate values required when the integrations are started.

        Phase 0 can load defaults without credentials so that configuration is
        testable before integrations exist. Call this method at an application
        entrypoint once the Slack integration is introduced.
        """

        required = {
            "SLACK_BOT_TOKEN": self.slack_bot_token,
            "SLACK_SIGNING_SECRET": self.slack_signing_secret,
            "SLACK_ALLOWED_CHANNEL_ID": self.slack_allowed_channel_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            joined = ", ".join(missing)
            raise ConfigError(f"Missing required runtime settings: {joined}")


_DEFAULTS: dict[str, str] = {
    "APP_TIMEZONE": "Asia/Tokyo",
    "WORKDAY_START": "10:00",
    "WORKDAY_END": "19:00",
    "WORKDAYS": "0,1,2,3,4",
    "MIN_SLOT_MINUTES": "30",
    "SLOT_GRANULARITY_MINUTES": "30",
    "BUSY_BUFFER_MINUTES": "30",
    "GOOGLE_CALENDAR_IDS": "primary",
    "GOOGLE_CALENDAR_TOKEN_FILE": "calendar_token.json",
    "GOOGLE_CLIENT_SECRET_FILE": "credentials.json",
    "LOG_LEVEL": "INFO",
}

_TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


def load_config(
    dotenv_path: str | Path = ".env",
    *,
    environ: Mapping[str, str] | None = None,
    require_runtime: bool = False,
) -> AppConfig:
    """Load and validate configuration.

    Values from ``environ`` (or the process environment) take precedence over
    values in the dotenv file. Reading dotenv values without mutating
    ``os.environ`` also makes repeated test runs deterministic.
    """

    runtime_values = dict(os.environ if environ is None else environ)
    dotenv_values_map = _load_dotenv_values(dotenv_path)

    def value(name: str, default: str | None = None) -> str | None:
        if name in runtime_values:
            return runtime_values[name]
        dotenv_value = dotenv_values_map.get(name)
        if dotenv_value is not None:
            return dotenv_value
        return default if default is not None else _DEFAULTS.get(name)

    config = AppConfig(
        timezone=_parse_timezone(value("APP_TIMEZONE")),
        workday_start=_parse_time(value("WORKDAY_START"), "WORKDAY_START"),
        workday_end=_parse_time(value("WORKDAY_END"), "WORKDAY_END"),
        workdays=_parse_workdays(value("WORKDAYS")),
        min_slot_minutes=_parse_positive_int(
            value("MIN_SLOT_MINUTES"), "MIN_SLOT_MINUTES"
        ),
        slot_granularity_minutes=_parse_positive_int(
            value("SLOT_GRANULARITY_MINUTES"),
            "SLOT_GRANULARITY_MINUTES",
        ),
        busy_buffer_minutes=_parse_non_negative_int(
            value("BUSY_BUFFER_MINUTES"),
            "BUSY_BUFFER_MINUTES",
            maximum=WEEK_MINUTES,
        ),
        google_calendar_ids=_parse_csv(
            value("GOOGLE_CALENDAR_IDS"), "GOOGLE_CALENDAR_IDS"
        ),
        google_calendar_token_file=_parse_path(
            value("GOOGLE_CALENDAR_TOKEN_FILE"),
            "GOOGLE_CALENDAR_TOKEN_FILE",
        ),
        google_calendar_token_json=_optional_text(value("GOOGLE_CALENDAR_TOKEN_JSON")),
        google_client_secret_file=_parse_path(
            value("GOOGLE_CLIENT_SECRET_FILE"),
            "GOOGLE_CLIENT_SECRET_FILE",
        ),
        slack_bot_token=_optional_text(value("SLACK_BOT_TOKEN")),
        slack_signing_secret=_optional_text(value("SLACK_SIGNING_SECRET")),
        slack_allowed_channel_id=_optional_text(value("SLACK_ALLOWED_CHANNEL_ID")),
        log_level=_parse_log_level(value("LOG_LEVEL")),
    )

    if config.workday_start >= config.workday_end:
        raise ConfigError("WORKDAY_START must be earlier than WORKDAY_END")

    if require_runtime:
        config.validate_runtime()
    return config


def _load_dotenv_values(path: str | Path) -> dict[str, str | None]:
    dotenv_path = Path(path)
    if not dotenv_path.is_file():
        return {}
    return dict(dotenv_values(dotenv_path))


def _parse_timezone(raw: str | None) -> ZoneInfo:
    value = _required_text(raw, "APP_TIMEZONE")
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"Invalid APP_TIMEZONE: {value}") from exc


def _parse_time(raw: str | None, name: str) -> time:
    value = _required_text(raw, name)
    if not _TIME_PATTERN.fullmatch(value):
        raise ConfigError(f"{name} must use HH:MM format")
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"Invalid {name}: {value}") from exc


def _parse_workdays(raw: str | None) -> tuple[int, ...]:
    value = _required_text(raw, "WORKDAYS")
    parts = [part.strip() for part in value.split(",")]
    if not parts or any(not part for part in parts):
        raise ConfigError("WORKDAYS must be a comma-separated list of weekdays")
    try:
        weekdays = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ConfigError("WORKDAYS must contain integers from 0 to 6") from exc
    if any(day < 0 or day > 6 for day in weekdays):
        raise ConfigError("WORKDAYS must contain integers from 0 to 6")
    if len(set(weekdays)) != len(weekdays):
        raise ConfigError("WORKDAYS must not contain duplicate weekdays")
    return weekdays


def _parse_positive_int(raw: str | None, name: str) -> int:
    value = _required_text(raw, name)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ConfigError(f"{name} must be greater than zero")
    return parsed


def _parse_non_negative_int(
    raw: str | None,
    name: str,
    *,
    maximum: int | None = None,
) -> int:
    value = _required_text(raw, name)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise ConfigError(f"{name} must be zero or greater")
    if maximum is not None and parsed > maximum:
        raise ConfigError(f"{name} must be at most {maximum}")
    return parsed


def _parse_csv(raw: str | None, name: str) -> tuple[str, ...]:
    value = _required_text(raw, name)
    items = tuple(item.strip() for item in value.split(","))
    if not items or any(not item for item in items):
        raise ConfigError(f"{name} must contain at least one non-empty value")
    return items


def _parse_path(raw: str | None, name: str) -> Path:
    return Path(_required_text(raw, name))


def _parse_log_level(raw: str | None) -> str:
    value = _required_text(raw, "LOG_LEVEL").upper()
    if value not in _LOG_LEVELS:
        choices = ", ".join(sorted(_LOG_LEVELS))
        raise ConfigError(f"LOG_LEVEL must be one of: {choices}")
    return value


def _optional_text(raw: str | None) -> str | None:
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def _required_text(raw: str | None, name: str) -> str:
    if not isinstance(raw, str):
        raise ConfigError(f"{name} must be text")
    value = (raw or "").strip()
    if not value:
        raise ConfigError(f"Missing required setting: {name}")
    return value


__all__ = ["AppConfig", "ConfigError", "load_config"]
