import inspect
import logging
from unittest.mock import MagicMock

import pytest
import sentry_sdk

import app.main
from app.config import settings
from app.sentry_config import _before_send, setup_sentry


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
