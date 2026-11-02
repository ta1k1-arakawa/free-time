"""Slack Events API adapter for the free-time application."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Callable

from slack_bolt import App
from slack_bolt.authorization.authorize_result import AuthorizeResult
from slack_sdk.errors import SlackApiError
from slack_sdk.web.client import WebClient

from free_time.app import FreeTimeApplication
from free_time.config import AppConfig

# Slack redelivers an event when the HTTP response is not returned within
# its acknowledgement window, and every redelivery carries the same message
# ``ts``. Remembering claimed message keys for an hour covers the whole
# retry schedule (immediate, +1 minute, +5 minutes, and delayed retries)
# while keeping the in-process store small.
_CLAIMED_EVENT_TTL = timedelta(hours=1)
_CLAIMED_EVENT_MAX_ENTRIES = 1024


def build_slack_app(
    config: AppConfig,
    application: FreeTimeApplication,
    *,
    clock: Callable[[], datetime] | None = None,
    client: WebClient | None = None,
) -> App:
    """Build a verified Bolt app that handles allowed-channel messages."""

    config.validate_runtime()
    now = clock or (lambda: datetime.now(config.timezone))

    claimed_events: dict[str, datetime] = {}
    claimed_events_lock = threading.Lock()

    def claim_event(event: dict) -> bool:
        """Return True only for the first delivery of a message event.

        Slack Events API delivery is at-least-once: when processing takes
        longer than Slack's acknowledgement window (for example on a Cloud
        Run cold start), Slack sends the same event again and, without this
        claim, each delivery would post another identical thread reply.
        The claim is keyed by channel and message ``ts``, which are stable
        across redeliveries of the same message. Events without a usable
        key cannot be deduplicated and are always processed.
        """

        channel = event.get("channel")
        timestamp = event.get("ts")
        if not isinstance(channel, str) or not isinstance(timestamp, str):
            return True
        key = f"{channel}:{timestamp}"
        current = now()
        with claimed_events_lock:
            expired = [
                claimed_key
                for claimed_key, claimed_at in claimed_events.items()
                if current - claimed_at > _CLAIMED_EVENT_TTL
            ]
            for claimed_key in expired:
                del claimed_events[claimed_key]
            if key in claimed_events:
                return False
            claimed_events[key] = current
            while len(claimed_events) > _CLAIMED_EVENT_MAX_ENTRIES:
                claimed_events.pop(next(iter(claimed_events)))
            return True

    def authorize(**_: object) -> AuthorizeResult:
        return AuthorizeResult(
            enterprise_id=None,
            team_id=None,
            bot_token=config.slack_bot_token,
        )

    before_authorize = None
    if client is not None:

        def inject_client(req: Any, next: Callable[[], Any]) -> Any:
            req.context["client"] = client
            return next()

        before_authorize = inject_client

    slack_app = App(
        token=config.slack_bot_token,
        authorize=authorize,
        before_authorize=before_authorize,
        signing_secret=config.slack_signing_secret,
        process_before_response=True,
        token_verification_enabled=False,
        request_verification_enabled=True,
        client=client,
    )

    @slack_app.event("message")
    def handle_message(event: dict, client: WebClient, logger: logging.Logger) -> None:
        if not _should_process_event(event, config.slack_allowed_channel_id):
            return
        if not claim_event(event):
            logger.info("Ignored duplicate Slack event delivery")
            return

        response_text = application.handle_command(event.get("text", ""), now=now())
        if response_text is None:
            return

        timestamp = event.get("ts")
        if not isinstance(timestamp, str):
            return
        thread_ts = event.get("thread_ts") or timestamp
        try:
            client.chat_postMessage(
                channel=event["channel"],
                text=response_text,
                thread_ts=thread_ts,
            )
        except SlackApiError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", "unknown")
            logger.error("Slack response failed (status=%s)", status)

    return slack_app


def _should_process_event(event: dict, allowed_channel_id: str | None) -> bool:
    if event.get("type") != "message":
        return False
    if event.get("subtype") is not None:
        return False
    if event.get("bot_id") or event.get("bot_profile"):
        return False
    return event.get("channel") == allowed_channel_id


__all__ = ["build_slack_app"]
