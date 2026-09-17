"""Google Calendar FreeBusy adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from webbrowser import Error as BrowserError
from zoneinfo import ZoneInfo

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauthlib.oauth2 import OAuth2Error
from requests import RequestException

from free_time.models import TimeRange

GOOGLE_CALENDAR_READONLY_SCOPES = ("https://www.googleapis.com/auth/calendar.readonly",)


class GoogleCalendarServiceError(RuntimeError):
    """Raised when Google Calendar credentials or FreeBusy data fail."""


@dataclass(frozen=True, slots=True)
class GoogleCalendarService:
    """Read busy intervals from Google Calendar FreeBusy."""

    calendar_ids: tuple[str, ...]
    token_file: Path
    token_json: str | None
    client_secret_file: Path
    timezone: str | ZoneInfo

    def get_busy_intervals(self, period: TimeRange) -> tuple[TimeRange, ...]:
        """Return unmerged busy intervals for all calendars in ``period``."""

        if not isinstance(period, TimeRange):
            raise GoogleCalendarServiceError("period must be a TimeRange")
        if not self.calendar_ids:
            raise GoogleCalendarServiceError("at least one calendar ID is required")

        try:
            credentials = self._load_credentials()
            calendar_service = build(
                "calendar",
                "v3",
                credentials=credentials,
                cache_discovery=False,
            )
            response = (
                calendar_service.freebusy()
                .query(body=self._build_request_body(period))
                .execute()
            )
            return self._parse_response(response)
        except GoogleCalendarServiceError:
            raise
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", "unknown")
            raise GoogleCalendarServiceError(
                f"Google Calendar API returned HTTP {status}"
            ) from exc
        except (GoogleAuthError, OSError, TypeError, ValueError) as exc:
            raise GoogleCalendarServiceError(
                "Failed to access Google Calendar"
            ) from exc

    def _load_credentials(self) -> Credentials:
        if self.token_json:
            credentials = self._load_credentials_from_json(self.token_json)
            return self._refresh_if_needed(credentials, persist=False)

        token_path = Path(self.token_file)
        if token_path.is_file():
            try:
                credentials = Credentials.from_authorized_user_file(
                    str(token_path),
                    GOOGLE_CALENDAR_READONLY_SCOPES,
                )
            except (GoogleAuthError, OSError, TypeError, ValueError, KeyError) as exc:
                raise GoogleCalendarServiceError(
                    "Failed to load Google Calendar token file"
                ) from exc
            return self._refresh_if_needed(credentials, persist=True)

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_secret_file),
                GOOGLE_CALENDAR_READONLY_SCOPES,
            )
            credentials = flow.run_local_server(port=0)
        except (
            BrowserError,
            GoogleAuthError,
            KeyError,
            OAuth2Error,
            OSError,
            RequestException,
            TypeError,
            ValueError,
            WSGITimeoutError,
        ) as exc:
            raise GoogleCalendarServiceError("Failed to complete Google OAuth") from exc

        self._persist_token(credentials, token_path)
        return credentials

    @staticmethod
    def _load_credentials_from_json(token_json: str) -> Credentials:
        try:
            info = json.loads(token_json)
            if not isinstance(info, dict):
                raise ValueError("authorized user JSON must be an object")
            return Credentials.from_authorized_user_info(
                info,
                GOOGLE_CALENDAR_READONLY_SCOPES,
            )
        except (GoogleAuthError, TypeError, ValueError, KeyError) as exc:
            raise GoogleCalendarServiceError(
                "Failed to load Google Calendar token JSON"
            ) from exc

    def _refresh_if_needed(
        self,
        credentials: Credentials,
        *,
        persist: bool,
    ) -> Credentials:
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except (GoogleAuthError, OSError, TypeError, ValueError) as exc:
                raise GoogleCalendarServiceError(
                    "Failed to refresh Google Calendar credentials"
                ) from exc
            if persist:
                self._persist_token(credentials, Path(self.token_file))
        if not credentials.valid:
            raise GoogleCalendarServiceError("Google Calendar credentials are invalid")
        return credentials

    @staticmethod
    def _persist_token(credentials: Credentials, token_path: Path) -> None:
        try:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            raise GoogleCalendarServiceError(
                "Failed to persist Google Calendar token"
            ) from exc

    def _build_request_body(self, period: TimeRange) -> dict[str, Any]:
        return {
            "timeMin": period.start.isoformat(),
            "timeMax": period.end.isoformat(),
            "timeZone": self._timezone_name(),
            "items": [{"id": calendar_id} for calendar_id in self.calendar_ids],
        }

    def _timezone_name(self) -> str:
        if isinstance(self.timezone, ZoneInfo):
            return self.timezone.key
        if isinstance(self.timezone, str):
            try:
                ZoneInfo(self.timezone)
            except (KeyError, TypeError, ValueError) as exc:
                raise GoogleCalendarServiceError(
                    "Invalid application timezone"
                ) from exc
            return self.timezone
        raise GoogleCalendarServiceError("Invalid application timezone")

    def _parse_response(self, response: Any) -> tuple[TimeRange, ...]:
        if not isinstance(response, dict):
            raise GoogleCalendarServiceError("Malformed FreeBusy response")
        calendars = response.get("calendars")
        if not isinstance(calendars, dict):
            raise GoogleCalendarServiceError("Malformed FreeBusy calendars response")

        intervals: list[TimeRange] = []
        for calendar_id in self.calendar_ids:
            calendar_data = calendars.get(calendar_id)
            if not isinstance(calendar_data, dict):
                raise GoogleCalendarServiceError("Malformed FreeBusy calendar response")
            self._raise_for_calendar_errors(calendar_data)
            busy = calendar_data.get("busy", [])
            if not isinstance(busy, list):
                raise GoogleCalendarServiceError("Malformed FreeBusy busy response")
            intervals.extend(self._parse_busy_entries(busy))
        return tuple(intervals)

    @staticmethod
    def _raise_for_calendar_errors(calendar_data: dict[str, Any]) -> None:
        errors = calendar_data.get("errors", [])
        if not isinstance(errors, list):
            raise GoogleCalendarServiceError("Malformed FreeBusy errors response")
        if errors:
            reason = "unknown"
            first_error = errors[0]
            if isinstance(first_error, dict) and isinstance(
                first_error.get("reason"), str
            ):
                reason = first_error["reason"]
            raise GoogleCalendarServiceError(
                f"Google Calendar FreeBusy returned calendar error: {reason}"
            )

    @staticmethod
    def _parse_busy_entries(entries: list[Any]) -> list[TimeRange]:
        intervals: list[TimeRange] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise GoogleCalendarServiceError("Malformed FreeBusy busy entry")
            start_text = entry.get("start")
            end_text = entry.get("end")
            if not isinstance(start_text, str) or not isinstance(end_text, str):
                raise GoogleCalendarServiceError("Malformed FreeBusy busy entry")
            try:
                start = datetime.fromisoformat(start_text)
                end = datetime.fromisoformat(end_text)
                if start.tzinfo is None or start.utcoffset() is None:
                    raise ValueError("busy start must be timezone-aware")
                if end.tzinfo is None or end.utcoffset() is None:
                    raise ValueError("busy end must be timezone-aware")
                intervals.append(TimeRange(start, end))
            except (KeyError, TypeError, ValueError) as exc:
                raise GoogleCalendarServiceError("Malformed FreeBusy datetime") from exc
        return intervals


__all__ = [
    "GOOGLE_CALENDAR_READONLY_SCOPES",
    "GoogleCalendarService",
    "GoogleCalendarServiceError",
]
