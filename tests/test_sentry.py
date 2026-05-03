import inspect
import json
import logging
from unittest.mock import MagicMock

import pytest
import sentry_sdk

import app.main
from app.config import settings
from app.sentry_config import _before_breadcrumb, _before_send, setup_sentry


@pytest.fixture
def mock_init(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(sentry_sdk, "init", mock)
    return mock


def test_init_noop_when_dsn_empty(mock_init, monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", "")
    setup_sentry()
    assert mock_init.call_count == 0


def test_init_called_with_expected_kwargs(mock_init, monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", "https://fake@example.com/1")
    monkeypatch.setattr(settings, "service_name", "ai-bot")

    setup_sentry()

    assert mock_init.call_count == 1
    kwargs = mock_init.call_args.kwargs
    assert kwargs["dsn"] == "https://fake@example.com/1"
    assert kwargs["environment"] == "ai-bot"
    assert kwargs["send_default_pii"] is False
    assert callable(kwargs["before_send"])
    assert callable(kwargs["before_breadcrumb"])
    li = next(
        i for i in kwargs["integrations"] if i.__class__.__name__ == "LoggingIntegration"
    )
    assert li._breadcrumb_handler.level == logging.INFO
    assert li._handler.level == logging.ERROR


def test_before_send_strips_system_prompt_from_extra():
    event = {
        "extra": {"system_prompt": "Ты опытный программист", "model": "Qwen3-0.6B"},
    }
    cleaned = _before_send(event, {})
    assert "system_prompt" not in cleaned["extra"]
    assert cleaned["extra"]["model"] == "Qwen3-0.6B"


def test_before_send_strips_system_prompt_from_breadcrumbs():
    event = {
        "breadcrumbs": {
            "values": [
                {
                    "type": "log",
                    "message": "starting_bot",
                    "data": {"system_prompt": "secret", "model": "Qwen3"},
                },
                {"type": "log", "message": "incoming_message", "data": {"chat_id": 1}},
            ],
        },
    }
    cleaned = _before_send(event, {})
    bcs = cleaned["breadcrumbs"]["values"]
    assert "system_prompt" not in bcs[0]["data"]
    assert bcs[0]["data"]["model"] == "Qwen3"
    assert bcs[1]["data"] == {"chat_id": 1}


def test_before_send_handles_event_without_extra_or_breadcrumbs():
    event = {"event_id": "abc"}
    cleaned = _before_send(event, {})
    assert cleaned == {"event_id": "abc"}


def test_main_run_calls_setup_sentry_after_setup_logging():
    src = inspect.getsource(app.main.run)
    logging_pos = src.find("setup_logging()")
    sentry_pos = src.find("setup_sentry()")
    assert logging_pos != -1, "setup_logging() must be called in run()"
    assert sentry_pos != -1, "setup_sentry() must be called in run()"
    assert sentry_pos > logging_pos, "setup_sentry() must run after setup_logging()"


# --- O-02.1 hotfix: PII leaks via structlog JSON message + Telegram URLs ---


def test_before_send_strips_system_prompt_from_breadcrumb_message_json():
    """structlog JSONRenderer puts whole event dict into bc['message'] string."""
    payload = {
        "event": "starting_bot",
        "model": "Qwen3-0.6B-GGUF",
        "system_prompt": "Ты опытный программист — secret",
        "service": "ai-bot",
    }
    event = {
        "breadcrumbs": {
            "values": [
                {"type": "log", "category": "__main__", "message": json.dumps(payload)},
            ],
        },
    }
    cleaned = _before_send(event, {})
    msg = cleaned["breadcrumbs"]["values"][0]["message"]
    assert "system_prompt" not in msg
    assert "secret" not in msg
    parsed = json.loads(msg)
    assert parsed["event"] == "starting_bot"
    assert parsed["model"] == "Qwen3-0.6B-GGUF"


def test_before_send_passes_non_json_message():
    event = {
        "breadcrumbs": {
            "values": [
                {"type": "default", "category": "telegram.ext", "message": "Application started"},
            ],
        },
    }
    cleaned = _before_send(event, {})
    assert cleaned["breadcrumbs"]["values"][0]["message"] == "Application started"


def test_before_send_handles_invalid_json_message():
    event = {
        "breadcrumbs": {
            "values": [
                {"type": "log", "message": '{"broken": '},
            ],
        },
    }
    cleaned = _before_send(event, {})
    assert cleaned["breadcrumbs"]["values"][0]["message"] == '{"broken": '


def test_before_breadcrumb_redacts_telegram_token_in_url():
    crumb = {
        "category": "httplib",
        "type": "http",
        "data": {
            "http.method": "POST",
            "url": "https://api.telegram.org/bot8634143010:AAF70a-pMhKZP7aSa7qMP2u83mF2H7qE2T0/getMe",
        },
    }
    cleaned = _before_breadcrumb(crumb, {})
    assert cleaned is not None
    assert "8634143010" not in cleaned["data"]["url"]
    assert "AAF70a-pMhKZP7aSa7qMP2u83mF2H7qE2T0" not in cleaned["data"]["url"]
    assert "[REDACTED]" in cleaned["data"]["url"]
    assert cleaned["data"]["url"].endswith("/getMe")


def test_before_breadcrumb_passes_through_non_telegram_urls():
    crumb = {
        "category": "httplib",
        "data": {"url": "http://lemonade:8000/api/v1/chat/completions"},
    }
    cleaned = _before_breadcrumb(crumb, {})
    assert cleaned["data"]["url"] == "http://lemonade:8000/api/v1/chat/completions"


def test_before_breadcrumb_passes_through_breadcrumbs_without_url():
    crumb = {"category": "log", "message": "hello"}
    cleaned = _before_breadcrumb(crumb, {})
    assert cleaned == {"category": "log", "message": "hello"}


def test_before_send_redacts_token_in_event_request_url():
    """Defense in depth: scrub URL even if it lands in event.request, not breadcrumb."""
    event = {
        "request": {
            "url": "https://api.telegram.org/bot8634143010:AAF70a-pMhKZP7aSa7qMP2u83mF2H7qE2T0/sendMessage",
        },
    }
    cleaned = _before_send(event, {})
    assert "8634143010" not in cleaned["request"]["url"]
    assert "[REDACTED]" in cleaned["request"]["url"]


def test_before_send_redacts_token_in_breadcrumb_data_url():
    """Same scrub applied through before_send (defense in depth) on breadcrumb URLs."""
    event = {
        "breadcrumbs": {
            "values": [
                {
                    "category": "httplib",
                    "data": {
                        "url": "https://api.telegram.org/bot123:ABCdef/getUpdates",
                    },
                },
            ],
        },
    }
    cleaned = _before_send(event, {})
    url = cleaned["breadcrumbs"]["values"][0]["data"]["url"]
    assert "ABCdef" not in url
    assert "[REDACTED]" in url
