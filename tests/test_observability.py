from unittest.mock import MagicMock, call

import pytest
import sentry_sdk
import structlog

from app.observability import bind_request_context, clear_request_context, new_trace_id


@pytest.fixture(autouse=True)
def cleanup_contextvars():
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


@pytest.fixture
def mock_set_tag(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(sentry_sdk, "set_tag", mock)
    return mock


@pytest.fixture
def mock_set_user(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(sentry_sdk, "set_user", mock)
    return mock


@pytest.fixture
def mock_isolation_scope(monkeypatch):
    scope = MagicMock()
    monkeypatch.setattr(sentry_sdk, "get_isolation_scope", MagicMock(return_value=scope))
    return scope


def test_new_trace_id_returns_uuid4_hex():
    tid = new_trace_id()
    assert isinstance(tid, str)
    assert len(tid) == 32
    int(tid, 16)


def test_bind_sets_sentry_tags(mock_set_tag):
    bind_request_context(trace_id="abc", update_id=42, user_id=7)

    calls = mock_set_tag.call_args_list
    assert call("trace_id", "abc") in calls
    assert call("update_id", 42) in calls
    assert call("user_id", 7) in calls


def test_bind_skips_none_optional_sentry_tags(mock_set_tag):
    bind_request_context(trace_id="abc")

    calls = mock_set_tag.call_args_list
    assert call("trace_id", "abc") in calls
    assert all(c.args[0] != "update_id" for c in calls)
    assert all(c.args[0] != "user_id" for c in calls)


def test_clear_resets_sentry_isolation_scope(mock_isolation_scope):
    clear_request_context()
    mock_isolation_scope.clear.assert_called_once()


def test_clear_drops_contextvars_bindings():
    bind_request_context(trace_id="abc", user_id=7)
    clear_request_context()
    ctx = structlog.contextvars.get_contextvars()
    assert "trace_id" not in ctx
    assert "user_id" not in ctx


# --- O-03: Sentry user context ---


def test_bind_calls_sentry_set_user_when_user_id_present(mock_set_user):
    bind_request_context(trace_id="abc", user_id=42, username="StasMura")
    assert mock_set_user.call_count == 1
    payload = mock_set_user.call_args.args[0]
    assert payload["id"] == 42
    assert payload["username"] == "StasMura"


def test_bind_skips_set_user_when_user_id_none(mock_set_user):
    bind_request_context(trace_id="abc")
    assert mock_set_user.call_count == 0


def test_bind_set_user_omits_username_when_none(mock_set_user):
    bind_request_context(trace_id="abc", user_id=42)
    payload = mock_set_user.call_args.args[0]
    assert payload["id"] == 42
    assert "username" not in payload
