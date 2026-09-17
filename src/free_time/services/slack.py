"""Slack Events API adapter for the free-time application."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from slack_bolt import App
from slack_bolt.authorization.authorize_result import AuthorizeResult
from slack_sdk.errors import SlackApiError
from slack_sdk.web.client import WebClient

from free_time.app import FreeTimeApplication
from free_time.config import AppConfig


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
