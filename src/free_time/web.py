"""FastAPI composition root for Slack Events API integration."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import FastAPI, Request
from slack_sdk.web.client import WebClient

from free_time.app import FreeTimeApplication
from free_time.config import AppConfig, load_config
from free_time.services.google_calendar import GoogleCalendarService
from free_time.services.slack import build_slack_app


def create_web_app(
    config: AppConfig | None = None,
    application: FreeTimeApplication | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    slack_client: WebClient | None = None,
) -> FastAPI:
    """Create the HTTP app without making network requests during startup."""

    resolved_config = config or load_config(require_runtime=True)
    resolved_application = application or _build_application(resolved_config)
    slack_app = build_slack_app(
        resolved_config,
        resolved_application,
        clock=clock,
        client=slack_client,
    )

    from slack_bolt.adapter.fastapi import SlackRequestHandler

    slack_handler = SlackRequestHandler(slack_app)
    api = FastAPI(title="free-time")

    @api.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/slack/events")
    async def slack_events(request: Request):
        return await slack_handler.handle(request)

    return api


def _build_application(config: AppConfig) -> FreeTimeApplication:
    calendar = GoogleCalendarService(
        calendar_ids=config.google_calendar_ids,
        token_file=config.google_calendar_token_file,
        token_json=config.google_calendar_token_json,
        client_secret_file=config.google_client_secret_file,
        timezone=config.timezone,
    )
    return FreeTimeApplication(config=config, calendar=calendar)


__all__ = ["create_web_app"]
