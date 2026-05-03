import json
import logging
import re

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from app.config import settings

_SENSITIVE_KEYS = ("system_prompt",)

# Telegram bot API embeds the token directly in the URL path:
#   https://api.telegram.org/bot<bot_id>:<auth_token>/<method>
# Sentry's HttpxIntegration logs every URL as a breadcrumb, so the token
# leaks on every getUpdates poll. Mask it before either source captures it.
_TG_TOKEN_RE = re.compile(r"/bot[A-Za-z0-9_:-]+(?=/)")
_TOKEN_REDACTION = "/bot[REDACTED]"


def _scrub_url(url: str) -> str:
    if not isinstance(url, str):
        return url
    return _TG_TOKEN_RE.sub(_TOKEN_REDACTION, url)


def _scrub_breadcrumb_message(bc: dict) -> None:
    msg = bc.get("message")
    if not isinstance(msg, str):
        return

    new_msg = _scrub_url(msg)

    if new_msg.lstrip().startswith("{"):
        try:
            parsed = json.loads(new_msg)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            changed = False
            for key in _SENSITIVE_KEYS:
                if parsed.pop(key, None) is not None:
                    changed = True
            if changed:
                new_msg = json.dumps(parsed, ensure_ascii=False)

    if new_msg != msg:
        bc["message"] = new_msg


def _scrub_breadcrumb_url(bc: dict) -> None:
    data = bc.get("data")
    if isinstance(data, dict) and "url" in data:
        data["url"] = _scrub_url(data["url"])


def _before_breadcrumb(crumb, _hint):
    _scrub_breadcrumb_url(crumb)
    _scrub_breadcrumb_message(crumb)
    return crumb


def _before_send(event, _hint):
    extra = event.get("extra")
    if isinstance(extra, dict):
        for key in _SENSITIVE_KEYS:
            extra.pop(key, None)

    request = event.get("request")
    if isinstance(request, dict) and "url" in request:
        request["url"] = _scrub_url(request["url"])

    logentry = event.get("logentry")
    if isinstance(logentry, dict) and isinstance(logentry.get("message"), str):
        logentry["message"] = _scrub_url(logentry["message"])

    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        for bc in breadcrumbs.get("values", []):
            data = bc.get("data")
            if isinstance(data, dict):
                for key in _SENSITIVE_KEYS:
                    data.pop(key, None)
            _scrub_breadcrumb_message(bc)
            _scrub_breadcrumb_url(bc)

    return event


def setup_sentry() -> None:
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.service_name,
        send_default_pii=False,
        before_send=_before_send,
        before_breadcrumb=_before_breadcrumb,
        integrations=[
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
