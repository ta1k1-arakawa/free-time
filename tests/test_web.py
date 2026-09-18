from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from slack_sdk.errors import SlackApiError
from slack_sdk.web.client import WebClient

from free_time.config import AppConfig, ConfigError
from free_time.services.slack import build_slack_app
from free_time.web import create_web_app

SIGNING_SECRET = "test-signing-secret"
TOKYO = ZoneInfo("Asia/Tokyo")


@dataclass
class FakeApplication:
    response: str | None = "📅 今週の空き時間\n\n候補"
    calls: list[tuple[str, datetime]] = field(default_factory=list)

    def handle_command(self, text: str, *, now: datetime) -> str | None:
        self.calls.append((text, now))
        return self.response


class FakeSlackClient(WebClient):
    def __init__(self, error: SlackApiError | None = None) -> None:
        super().__init__(token="xoxb-test-token")
        self.calls: list[dict[str, str]] = []
        self.error = error

    def chat_postMessage(self, **kwargs: str) -> dict[str, Any]:
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)
        return {"ok": True}


def config(*, allowed_channel: str = "ALLOWED_CHANNEL") -> AppConfig:
    return AppConfig(
        timezone=TOKYO,
        workday_start=datetime.min.time().replace(hour=10),
        workday_end=datetime.min.time().replace(hour=19),
        workdays=(0, 1, 2, 3, 4),
        min_slot_minutes=30,
        slot_granularity_minutes=30,
        google_calendar_ids=("primary",),
        google_calendar_token_file=Path("calendar_token.json"),
        google_client_secret_file=Path("credentials.json"),
        slack_bot_token="xoxb-test-token",
        slack_signing_secret=SIGNING_SECRET,
        slack_allowed_channel_id=allowed_channel,
    )


def fixed_now() -> datetime:
    return datetime(2026, 9, 17, 14, 12, tzinfo=TOKYO)


def signed_request(
    client: TestClient,
    payload: dict[str, Any],
    *,
    signature: str | None = None,
) -> Any:
    if payload.get("type") == "message":
        payload = {
            "type": "event_callback",
            "event": payload,
        }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    if signature is None:
        base = f"v0:{timestamp}:".encode() + body
        digest = hmac.new(SIGNING_SECRET.encode(), base, hashlib.sha256).hexdigest()
        signature = f"v0={digest}"
    return client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": timestamp,
            "x-slack-signature": signature,
        },
    )


def build_test_client(
    application: FakeApplication,
    slack_client: FakeSlackClient,
    *,
    clock=fixed_now,
) -> TestClient:
    api = create_web_app(
        config=config(),
        application=application,  # type: ignore[arg-type]
        clock=clock,
        slack_client=slack_client,  # type: ignore[arg-type]
    )
    return TestClient(api)


def test_health_returns_ok_without_external_calls() -> None:
    application = FakeApplication()
    slack_client = FakeSlackClient()
    client = build_test_client(application, slack_client)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert application.calls == []
    assert slack_client.calls == []


def test_valid_url_verification_returns_challenge() -> None:
    application = FakeApplication()
    slack_client = FakeSlackClient()
    client = build_test_client(application, slack_client)

    response = signed_request(
        client,
        {"type": "url_verification", "challenge": "challenge-value"},
    )

    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-value"}
    assert application.calls == []
    assert slack_client.calls == []


def test_invalid_signature_is_rejected_without_listener_execution() -> None:
    application = FakeApplication()
    slack_client = FakeSlackClient()
    client = build_test_client(application, slack_client)

    response = signed_request(
        client,
        {
            "type": "message",
            "channel": "ALLOWED_CHANNEL",
            "text": "今週",
            "ts": "123.456",
        },
        signature="v0=invalid",
    )

    assert response.status_code < 200 or response.status_code >= 300
    assert application.calls == []
    assert slack_client.calls == []


def test_allowed_message_calls_application_and_replies_to_top_level_thread() -> None:
    application = FakeApplication()
    slack_client = FakeSlackClient()
    client = build_test_client(application, slack_client)

    response = signed_request(
        client,
        {
            "type": "message",
            "channel": "ALLOWED_CHANNEL",
            "user": "U123",
            "text": "今週",
            "ts": "123.456",
        },
    )

    assert response.status_code == 200
    assert application.calls == [("今週", fixed_now())]
    assert slack_client.calls == [
        {
            "channel": "ALLOWED_CHANNEL",
            "text": "📅 今週の空き時間\n\n候補",
            "thread_ts": "123.456",
        }
    ]


def test_existing_thread_is_preserved() -> None:
    application = FakeApplication()
    slack_client = FakeSlackClient()
    client = build_test_client(application, slack_client)

    response = signed_request(
        client,
        {
            "type": "message",
            "channel": "ALLOWED_CHANNEL",
            "user": "U123",
            "text": "来週",
            "ts": "123.999",
            "thread_ts": "123.456",
        },
    )

    assert response.status_code == 200
    assert slack_client.calls[0]["thread_ts"] == "123.456"


@pytest.mark.parametrize(
    "event",
    [
        {
            "type": "message",
            "channel": "OTHER_CHANNEL",
            "text": "今週",
            "ts": "123.456",
        },
        {
            "type": "message",
            "channel": "ALLOWED_CHANNEL",
            "subtype": "bot_message",
            "text": "今週",
            "ts": "123.456",
        },
        {
            "type": "message",
            "channel": "ALLOWED_CHANNEL",
            "bot_id": "B123",
            "text": "今週",
            "ts": "123.456",
        },
        {
            "type": "message",
            "channel": "ALLOWED_CHANNEL",
            "subtype": "message_changed",
            "text": "今週",
            "ts": "123.456",
        },
    ],
)
def test_ignored_events_do_not_call_application_or_slack(event: dict[str, str]) -> None:
    application = FakeApplication()
    slack_client = FakeSlackClient()
    client = build_test_client(application, slack_client)

    response = signed_request(client, event)

    assert response.status_code == 200
    assert application.calls == []
    assert slack_client.calls == []


@pytest.mark.parametrize("text", ["今週は忙しい", "こんにちは"])
def test_unknown_command_does_not_post(text: str) -> None:
    application = FakeApplication(response=None)
    slack_client = FakeSlackClient()
    client = build_test_client(application, slack_client)

    response = signed_request(
        client,
        {
            "type": "message",
            "channel": "ALLOWED_CHANNEL",
            "text": text,
            "ts": "123.456",
        },
    )

    assert response.status_code == 200
    assert application.calls == [(text, fixed_now())]
    assert slack_client.calls == []


def test_listener_passes_timezone_aware_now_to_application() -> None:
    application = FakeApplication(response=None)
    slack_client = FakeSlackClient()

    def injected_now() -> datetime:
        return fixed_now()

    client = build_test_client(application, slack_client, clock=injected_now)

    signed_request(
        client,
        {
            "type": "message",
            "channel": "ALLOWED_CHANNEL",
            "text": "今週",
            "ts": "123.456",
        },
    )

    assert application.calls[0][1].tzinfo == TOKYO
    assert application.calls[0][1] == fixed_now()


def test_runtime_config_is_required_for_slack_factory() -> None:
    invalid = config()
    invalid = AppConfig(
        timezone=invalid.timezone,
        workday_start=invalid.workday_start,
        workday_end=invalid.workday_end,
        workdays=invalid.workdays,
        min_slot_minutes=invalid.min_slot_minutes,
        slot_granularity_minutes=invalid.slot_granularity_minutes,
        google_calendar_ids=invalid.google_calendar_ids,
        google_calendar_token_file=invalid.google_calendar_token_file,
        google_client_secret_file=invalid.google_client_secret_file,
    )

    with pytest.raises(ConfigError, match="SLACK_BOT_TOKEN"):
        build_slack_app(invalid, FakeApplication())  # type: ignore[arg-type]


def test_slack_api_error_is_not_retried_or_exposed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    application = FakeApplication()
    error = SlackApiError(
        message="private response body",
        response={"ok": False, "error": "invalid_auth"},
    )
    slack_client = FakeSlackClient(error=error)
    client = build_test_client(application, slack_client)

    response = signed_request(
        client,
        {
            "type": "message",
            "channel": "ALLOWED_CHANNEL",
            "text": "今週",
            "ts": "123.456",
        },
    )

    assert response.status_code == 200
    assert len(application.calls) == 1
    assert "private response body" not in caplog.text
