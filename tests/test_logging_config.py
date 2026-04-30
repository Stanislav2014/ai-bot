import json
import logging

import pytest
import structlog

from app.config import settings
from app.logging_config import setup_logging


@pytest.fixture(autouse=True)
def isolate_logging(monkeypatch, tmp_path):
    """Isolate root handlers + structlog state per test."""
    monkeypatch.setattr(settings, "log_file", str(tmp_path / "test.log"))
    yield
    logging.getLogger().handlers.clear()
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()


def _last_json(capsys) -> dict:
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "no log output captured"
    return json.loads(out[-1])


def test_log_is_valid_json(capsys):
    setup_logging()
    structlog.get_logger().info("test_event")
    record = _last_json(capsys)
    assert isinstance(record, dict)


def test_log_contains_required_fields(capsys):
    setup_logging()
    structlog.get_logger().info("test_event")
    record = _last_json(capsys)
    assert "timestamp" in record
    assert record["level"] == "info"
    assert record["event"] == "test_event"
    assert "service" in record


def test_service_field_is_ai_bot_by_default(capsys):
    setup_logging()
    structlog.get_logger().info("evt")
    record = _last_json(capsys)
    assert record["service"] == "ai-bot"


def test_service_field_respects_settings(capsys, monkeypatch):
    monkeypatch.setattr(settings, "service_name", "custom-service")
    setup_logging()
    structlog.get_logger().info("evt")
    record = _last_json(capsys)
    assert record["service"] == "custom-service"


def test_trace_id_propagates_via_contextvars(capsys):
    setup_logging()
    structlog.contextvars.bind_contextvars(trace_id="abc123")
    structlog.get_logger().info("after_bind")
    record = _last_json(capsys)
    assert record["trace_id"] == "abc123"


def test_user_id_propagates_via_contextvars(capsys):
    setup_logging()
    structlog.contextvars.bind_contextvars(user_id=42)
    structlog.get_logger().info("with_user")
    record = _last_json(capsys)
    assert record["user_id"] == 42


def test_clear_contextvars_drops_trace_id(capsys):
    setup_logging()
    structlog.contextvars.bind_contextvars(trace_id="xyz")
    structlog.contextvars.clear_contextvars()
    structlog.get_logger().info("after_clear")
    record = _last_json(capsys)
    assert "trace_id" not in record


def test_error_level_is_recorded(capsys):
    setup_logging()
    structlog.get_logger().error("oops", reason="boom")
    record = _last_json(capsys)
    assert record["level"] == "error"
    assert record["event"] == "oops"
    assert record["reason"] == "boom"
