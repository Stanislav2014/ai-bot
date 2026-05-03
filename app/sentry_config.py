import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from app.config import settings


_SENSITIVE_KEYS = ("system_prompt",)


def _before_send(event, _hint):
    extra = event.get("extra")
    if isinstance(extra, dict):
        for key in _SENSITIVE_KEYS:
            extra.pop(key, None)

    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        for bc in breadcrumbs.get("values", []):
            data = bc.get("data")
            if isinstance(data, dict):
                for key in _SENSITIVE_KEYS:
                    data.pop(key, None)

    return event


def setup_sentry() -> None:
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.service_name,
        send_default_pii=False,
        before_send=_before_send,
        integrations=[
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
