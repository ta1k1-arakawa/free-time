from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from free_time.models import TimeRange
from free_time.services.google_calendar import (
    GOOGLE_CALENDAR_READONLY_SCOPES,
    GoogleCalendarService,
    GoogleCalendarServiceError,
)

TOKYO = ZoneInfo("Asia/Tokyo")


def period() -> TimeRange:
    return TimeRange(
        datetime(2026, 9, 14, tzinfo=TOKYO),
        datetime(2026, 9, 21, tzinfo=TOKYO),
    )


def service(
    tmp_path: Path,
    *,
    calendar_ids: tuple[str, ...] = ("primary",),
    token_json: str | None = "{}",
) -> GoogleCalendarService:
    return GoogleCalendarService(
        calendar_ids=calendar_ids,
        token_file=tmp_path / "calendar_token.json",
        token_json=token_json,
        client_secret_file=tmp_path / "credentials.json",
        timezone="Asia/Tokyo",
    )


def fake_credentials(*, expired: bool = False) -> MagicMock:
    credentials = MagicMock(spec=Credentials)
    credentials.expired = expired
    credentials.refresh_token = "refresh-token" if expired else None
    credentials.valid = True
    credentials.to_json.return_value = '{"token": "fake"}'
    return credentials


def fake_client(response: dict[str, object]) -> MagicMock:
    client = MagicMock()
    client.freebusy.return_value.query.return_value.execute.return_value = response
    return client


def test_token_json_has_priority_over_token_file(tmp_path: Path) -> None:
    token_file = tmp_path / "calendar_token.json"
    token_file.write_text("file-token", encoding="utf-8")
    credentials = fake_credentials()
    client = fake_client({"calendars": {"primary": {"busy": []}}})

    with (
        patch(
            "free_time.services.google_calendar.Credentials.from_authorized_user_info",
            return_value=credentials,
        ) as from_info,
        patch(
            "free_time.services.google_calendar.Credentials.from_authorized_user_file"
        ) as from_file,
        patch("free_time.services.google_calendar.build", return_value=client),
    ):
        result = service(tmp_path, token_json='{"source": "env"}').get_busy_intervals(
            period()
        )

    assert result == ()
    from_info.assert_called_once_with(
        {"source": "env"}, GOOGLE_CALENDAR_READONLY_SCOPES
    )
    from_file.assert_not_called()


def test_token_file_is_used_when_token_json_is_absent(tmp_path: Path) -> None:
    token_file = tmp_path / "calendar_token.json"
    token_file.write_text("fake-token", encoding="utf-8")
    credentials = fake_credentials()
    client = fake_client({"calendars": {"primary": {"busy": []}}})

    with (
        patch(
            "free_time.services.google_calendar.Credentials.from_authorized_user_file",
            return_value=credentials,
        ) as from_file,
        patch("free_time.services.google_calendar.build", return_value=client),
    ):
        result = service(tmp_path, token_json=None).get_busy_intervals(period())

    assert result == ()
    from_file.assert_called_once_with(str(token_file), GOOGLE_CALENDAR_READONLY_SCOPES)


def test_installed_app_flow_is_used_when_no_token_exists(tmp_path: Path) -> None:
    credentials = fake_credentials()
    client = fake_client({"calendars": {"primary": {"busy": []}}})
    flow = MagicMock()
    flow.run_local_server.return_value = credentials

    with (
        patch(
            "free_time.services.google_calendar.InstalledAppFlow.from_client_secrets_file",
            return_value=flow,
        ) as from_secrets,
        patch("free_time.services.google_calendar.build", return_value=client),
    ):
        result = service(tmp_path, token_json=None).get_busy_intervals(period())

    assert result == ()
    from_secrets.assert_called_once_with(
        str(tmp_path / "credentials.json"), GOOGLE_CALENDAR_READONLY_SCOPES
    )
    flow.run_local_server.assert_called_once_with(port=0)
    assert (tmp_path / "calendar_token.json").read_text(encoding="utf-8") == (
        '{"token": "fake"}'
    )


def test_expired_file_credential_is_refreshed_and_persisted(tmp_path: Path) -> None:
    token_file = tmp_path / "calendar_token.json"
    token_file.write_text("old-token", encoding="utf-8")
    credentials = fake_credentials(expired=True)
    client = fake_client({"calendars": {"primary": {"busy": []}}})

    with (
        patch(
            "free_time.services.google_calendar.Credentials.from_authorized_user_file",
            return_value=credentials,
        ),
        patch("free_time.services.google_calendar.build", return_value=client),
    ):
        service(tmp_path, token_json=None).get_busy_intervals(period())

    credentials.refresh.assert_called_once()
    assert token_file.read_text(encoding="utf-8") == '{"token": "fake"}'


def test_expired_env_credential_is_not_persisted(tmp_path: Path) -> None:
    token_file = tmp_path / "calendar_token.json"
    credentials = fake_credentials(expired=True)
    client = fake_client({"calendars": {"primary": {"busy": []}}})

    with (
        patch(
            "free_time.services.google_calendar.GoogleCalendarService._load_credentials_from_json",
            return_value=credentials,
        ),
        patch("free_time.services.google_calendar.build", return_value=client),
    ):
        service(tmp_path, token_json="env-token").get_busy_intervals(period())

    credentials.refresh.assert_called_once()
    credentials.to_json.assert_not_called()
    assert not token_file.exists()


def test_freebusy_uses_one_request_with_all_calendars(tmp_path: Path) -> None:
    calendar_ids = ("primary", "calendar-b", "calendar-c")
    response = {
        "calendars": {calendar_id: {"busy": []} for calendar_id in calendar_ids}
    }
    client = fake_client(response)

    with (
        patch.object(
            GoogleCalendarService, "_load_credentials", return_value=fake_credentials()
        ),
        patch("free_time.services.google_calendar.build", return_value=client),
    ):
        result = service(tmp_path, calendar_ids=calendar_ids).get_busy_intervals(
            period()
        )

    assert result == ()
    query = client.freebusy.return_value.query
    query.assert_called_once_with(
        body={
            "timeMin": "2026-09-14T00:00:00+09:00",
            "timeMax": "2026-09-21T00:00:00+09:00",
            "timeZone": "Asia/Tokyo",
            "items": [{"id": value} for value in calendar_ids],
        }
    )
    client.freebusy.return_value.query.return_value.execute.assert_called_once_with()


def test_single_calendar_busy_intervals_are_converted(tmp_path: Path) -> None:
    response = {
        "calendars": {
            "primary": {
                "busy": [
                    {
                        "start": "2026-09-18T10:00:00+09:00",
                        "end": "2026-09-18T11:00:00+09:00",
                    },
                    {
                        "start": "2026-09-18T13:00:00+09:00",
                        "end": "2026-09-18T14:30:00+09:00",
                    },
                ]
            }
        }
    }
    service_instance = service(tmp_path)

    result = service_instance._parse_response(response)

    assert result == (
        TimeRange(
            datetime(2026, 9, 18, 10, tzinfo=TOKYO),
            datetime(2026, 9, 18, 11, tzinfo=TOKYO),
        ),
        TimeRange(
            datetime(2026, 9, 18, 13, tzinfo=TOKYO),
            datetime(2026, 9, 18, 14, 30, tzinfo=TOKYO),
        ),
    )


def test_multiple_calendar_intervals_are_flattened_without_merging(
    tmp_path: Path,
) -> None:
    response = {
        "calendars": {
            "calendar-a": {
                "busy": [
                    {
                        "start": "2026-09-18T10:00:00+09:00",
                        "end": "2026-09-18T12:00:00+09:00",
                    }
                ]
            },
            "calendar-b": {
                "busy": [
                    {
                        "start": "2026-09-18T11:00:00+09:00",
                        "end": "2026-09-18T13:00:00+09:00",
                    }
                ]
            },
        }
    }

    result = service(
        tmp_path, calendar_ids=("calendar-a", "calendar-b")
    )._parse_response(response)

    assert len(result) == 2
    assert result[0].end == datetime(2026, 9, 18, 12, tzinfo=TOKYO)
    assert result[1].start == datetime(2026, 9, 18, 11, tzinfo=TOKYO)


@pytest.mark.parametrize(
    ("start_text", "end_text", "expected_start"),
    [
        ("2026-09-18T01:00:00Z", "2026-09-18T02:00:00Z", datetime(2026, 9, 18, 1)),
        (
            "2026-09-18T10:00:00+09:00",
            "2026-09-18T11:00:00+09:00",
            datetime(2026, 9, 18, 10),
        ),
    ],
)
def test_response_timezones_are_preserved(
    tmp_path: Path,
    start_text: str,
    end_text: str,
    expected_start: datetime,
) -> None:
    response = {
        "calendars": {"primary": {"busy": [{"start": start_text, "end": end_text}]}}
    }

    result = service(tmp_path)._parse_response(response)

    assert result[0].start.isoformat() == start_text.replace("Z", "+00:00")
    assert result[0].start.replace(tzinfo=None) == expected_start
    assert result[0].start.tzinfo is not None


def test_calendar_level_error_fails_closed(tmp_path: Path) -> None:
    response = {
        "calendars": {
            "primary": {
                "errors": [{"domain": "calendar", "reason": "notFound"}],
                "busy": [],
            }
        }
    }

    with pytest.raises(GoogleCalendarServiceError, match="notFound"):
        service(tmp_path)._parse_response(response)


@pytest.mark.parametrize(
    "response",
    [
        {"calendars": {"primary": {"busy": [{"end": "2026-09-18T11:00:00Z"}]}}},
        {"calendars": {"primary": {"busy": [{"start": "2026-09-18T10:00:00Z"}]}}},
        {
            "calendars": {
                "primary": {
                    "busy": [
                        {
                            "start": "2026-09-18 10:00:00",
                            "end": "2026-09-18T11:00:00Z",
                        }
                    ]
                }
            }
        },
        {
            "calendars": {
                "primary": {
                    "busy": [
                        {
                            "start": "2026-09-18T11:00:00Z",
                            "end": "2026-09-18T10:00:00Z",
                        }
                    ]
                }
            }
        },
    ],
)
def test_malformed_busy_entries_raise_project_error(
    tmp_path: Path, response: dict[str, object]
) -> None:
    with pytest.raises(GoogleCalendarServiceError):
        service(tmp_path)._parse_response(response)


@pytest.mark.parametrize(
    "response",
    [
        {"calendars": []},
        {"calendars": {"primary": {"busy": {}}}},
        {"calendars": {"primary": {"errors": "invalid", "busy": []}}},
        {"calendars": {"primary": {"busy": ["invalid"]}}},
    ],
)
def test_malformed_freebusy_response_raises_project_error(
    tmp_path: Path, response: dict[str, object]
) -> None:
    with pytest.raises(GoogleCalendarServiceError):
        service(tmp_path)._parse_response(response)


def test_http_error_is_wrapped_without_response_body(tmp_path: Path) -> None:
    response = MagicMock(status=403)
    error = HttpError(response, b"secret response body")
    client = MagicMock()
    client.freebusy.return_value.query.return_value.execute.side_effect = error

    with (
        patch.object(
            GoogleCalendarService, "_load_credentials", return_value=fake_credentials()
        ),
        patch("free_time.services.google_calendar.build", return_value=client),
        pytest.raises(GoogleCalendarServiceError, match="HTTP 403") as raised,
    ):
        service(tmp_path).get_busy_intervals(period())

    assert "secret response body" not in str(raised.value)


def test_invalid_token_json_is_wrapped_without_json_body(tmp_path: Path) -> None:
    secret = '{"refresh_token":"super-secret"'

    with pytest.raises(GoogleCalendarServiceError) as raised:
        service(tmp_path, token_json=secret).get_busy_intervals(period())

    assert secret not in str(raised.value)


def test_invalid_period_is_rejected_before_api_access(tmp_path: Path) -> None:
    with pytest.raises(GoogleCalendarServiceError, match="period"):
        service(tmp_path).get_busy_intervals("not a period")  # type: ignore[arg-type]


def test_empty_calendar_ids_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(GoogleCalendarServiceError, match="calendar ID"):
        service(tmp_path, calendar_ids=()).get_busy_intervals(period())


def test_missing_requested_calendar_is_malformed(tmp_path: Path) -> None:
    response = {"calendars": {}}

    with pytest.raises(GoogleCalendarServiceError, match="calendar response"):
        service(tmp_path)._parse_response(response)


def test_non_mapping_response_is_malformed(tmp_path: Path) -> None:
    with pytest.raises(GoogleCalendarServiceError, match="FreeBusy response"):
        service(tmp_path)._parse_response([])


def test_calendar_error_without_reason_uses_safe_fallback(tmp_path: Path) -> None:
    response = {"calendars": {"primary": {"errors": [{}], "busy": []}}}

    with pytest.raises(GoogleCalendarServiceError, match="unknown"):
        service(tmp_path)._parse_response(response)


def test_build_error_is_wrapped(tmp_path: Path) -> None:
    with (
        patch.object(
            GoogleCalendarService, "_load_credentials", return_value=fake_credentials()
        ),
        patch(
            "free_time.services.google_calendar.build", side_effect=OSError("network")
        ),
        pytest.raises(GoogleCalendarServiceError, match="access Google Calendar"),
    ):
        service(tmp_path).get_busy_intervals(period())


def test_token_file_loader_error_is_wrapped(tmp_path: Path) -> None:
    token_file = tmp_path / "calendar_token.json"
    token_file.write_text("fake-token", encoding="utf-8")

    with (
        patch(
            "free_time.services.google_calendar.Credentials.from_authorized_user_file",
            side_effect=OSError("file read failed"),
        ),
        pytest.raises(GoogleCalendarServiceError, match="token file"),
    ):
        service(tmp_path, token_json=None).get_busy_intervals(period())


def test_oauth_failure_is_wrapped(tmp_path: Path) -> None:
    flow = MagicMock()
    flow.run_local_server.side_effect = OSError("oauth failed")

    with (
        patch(
            "free_time.services.google_calendar.InstalledAppFlow.from_client_secrets_file",
            return_value=flow,
        ),
        pytest.raises(GoogleCalendarServiceError, match="complete Google OAuth"),
    ):
        service(tmp_path, token_json=None).get_busy_intervals(period())


def test_refresh_failure_is_wrapped(tmp_path: Path) -> None:
    token_file = tmp_path / "calendar_token.json"
    token_file.write_text("old-token", encoding="utf-8")
    credentials = fake_credentials(expired=True)
    credentials.refresh.side_effect = OSError("refresh failed")

    with (
        patch(
            "free_time.services.google_calendar.Credentials.from_authorized_user_file",
            return_value=credentials,
        ),
        pytest.raises(GoogleCalendarServiceError, match="refresh"),
    ):
        service(tmp_path, token_json=None).get_busy_intervals(period())


def test_invalid_credentials_are_rejected(tmp_path: Path) -> None:
    credentials = fake_credentials()
    credentials.valid = False

    with pytest.raises(GoogleCalendarServiceError, match="credentials are invalid"):
        service(tmp_path)._refresh_if_needed(credentials, persist=False)


def test_token_persistence_failure_is_wrapped(tmp_path: Path) -> None:
    credentials = fake_credentials()
    credentials.to_json.side_effect = OSError("write failed")

    with pytest.raises(GoogleCalendarServiceError, match="persist"):
        GoogleCalendarService._persist_token(credentials, tmp_path / "token.json")


def test_invalid_timezone_is_rejected(tmp_path: Path) -> None:
    invalid = GoogleCalendarService(
        calendar_ids=("primary",),
        token_file=tmp_path / "token.json",
        token_json="{}",
        client_secret_file=tmp_path / "credentials.json",
        timezone="Not/A-Timezone",
    )

    with pytest.raises(GoogleCalendarServiceError, match="timezone"):
        invalid._timezone_name()


def test_zoneinfo_timezone_is_supported(tmp_path: Path) -> None:
    tokyo_service = service(tmp_path)

    assert tokyo_service._timezone_name() == "Asia/Tokyo"
