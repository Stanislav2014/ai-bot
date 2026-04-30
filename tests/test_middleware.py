import json
import logging
import re
from datetime import datetime, timezone

import pytest
import structlog
from telegram import CallbackQuery, Chat, Message, Update, User

from app.bot.middleware import LoggingMiddleware
from app.config import settings
from app.logging_config import setup_logging


HEX32 = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture(autouse=True)
def isolate_logging(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "log_file", str(tmp_path / "test.log"))
    yield
    logging.getLogger().handlers.clear()
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()


def _make_message_update(
    *, update_id: int = 1, user_id: int = 42, username: str = "u", text: str = "hi"
) -> Update:
    user = User(id=user_id, first_name="Test", is_bot=False, username=username)
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        text=text,
    )
    return Update(update_id=update_id, message=msg)


def _make_callback_update(*, update_id: int = 2, user_id: int = 99) -> Update:
    user = User(id=user_id, first_name="CB", is_bot=False, username="cb")
    cb = CallbackQuery(
        id="cbq-1",
        from_user=user,
        chat_instance="ci",
        data="model:foo",
    )
    return Update(update_id=update_id, callback_query=cb)


def _logs(capsys) -> list[dict]:
    out = capsys.readouterr().out.strip().splitlines()
    return [json.loads(line) for line in out]


def test_check_update_returns_false(capsys):
    setup_logging()
    mw = LoggingMiddleware()
    assert mw.check_update(_make_message_update()) is False


def test_check_update_binds_uuid_trace_id(capsys):
    setup_logging()
    mw = LoggingMiddleware()
    mw.check_update(_make_message_update())
    structlog.get_logger().info("downstream")

    records = _logs(capsys)
    incoming, downstream = records[0], records[-1]
    assert HEX32.match(incoming["trace_id"]), incoming["trace_id"]
    assert downstream["trace_id"] == incoming["trace_id"]


def test_two_updates_get_different_trace_ids(capsys):
    setup_logging()
    mw = LoggingMiddleware()

    mw.check_update(_make_message_update(update_id=1))
    structlog.get_logger().info("after_first")
    first_trace = _logs(capsys)[-1]["trace_id"]

    mw.check_update(_make_message_update(update_id=2))
    structlog.get_logger().info("after_second")
    second_trace = _logs(capsys)[-1]["trace_id"]

    assert first_trace != second_trace
    assert HEX32.match(second_trace)


def test_check_update_binds_user_id_from_message(capsys):
    setup_logging()
    mw = LoggingMiddleware()
    mw.check_update(_make_message_update(user_id=777))
    structlog.get_logger().info("downstream")
    record = _logs(capsys)[-1]
    assert record["user_id"] == 777


def test_check_update_binds_user_id_from_callback_query(capsys):
    setup_logging()
    mw = LoggingMiddleware()
    mw.check_update(_make_callback_update(user_id=555))
    structlog.get_logger().info("downstream")
    record = _logs(capsys)[-1]
    assert record["user_id"] == 555


def test_check_update_binds_update_id(capsys):
    setup_logging()
    mw = LoggingMiddleware()
    mw.check_update(_make_message_update(update_id=12345))
    structlog.get_logger().info("downstream")
    record = _logs(capsys)[-1]
    assert record["update_id"] == 12345


def test_incoming_message_log_has_required_fields(capsys):
    setup_logging()
    mw = LoggingMiddleware()
    mw.check_update(_make_message_update(text="hello world"))
    record = _logs(capsys)[0]
    assert record["event"] == "incoming_message"
    assert record["service"] == "ai-bot"
    assert record["text"] == "hello world"
    assert "trace_id" in record
    assert "user_id" in record


def test_check_update_clears_previous_contextvars(capsys):
    setup_logging()
    structlog.contextvars.bind_contextvars(trace_id="leftover", user_id=999)
    mw = LoggingMiddleware()
    mw.check_update(_make_message_update(user_id=42))
    structlog.get_logger().info("downstream")
    record = _logs(capsys)[-1]
    assert record["trace_id"] != "leftover"
    assert record["user_id"] == 42


def test_non_update_object_does_not_bind(capsys):
    setup_logging()
    mw = LoggingMiddleware()
    assert mw.check_update("not an update") is False
    structlog.get_logger().info("after")
    record = _logs(capsys)[-1]
    assert "trace_id" not in record
