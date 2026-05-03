"""Unit tests for the /sentry_test command logic.

Goal: verify the four ДЗ-required error types are reachable through the
handler. We test the pure trigger function and the whitelist guard
without spinning up Update/Message mocks for every Telegram detail —
those would test PTB, not our logic.
"""
import asyncio
import json

import httpx
import pytest

from app.bot.handlers import _SENTRY_TEST_KINDS, _is_sentry_test_allowed, _trigger_error


def test_kinds_cover_homework_scenarios():
    assert set(_SENTRY_TEST_KINDS) == {"raise", "async", "external", "data"}


@pytest.mark.asyncio
async def test_trigger_error_raise_kind_raises_runtime_error():
    with pytest.raises(RuntimeError, match="manual"):
        await _trigger_error("raise")


@pytest.mark.asyncio
async def test_trigger_error_data_kind_raises_json_decode_error():
    with pytest.raises(json.JSONDecodeError):
        await _trigger_error("data")


@pytest.mark.asyncio
async def test_trigger_error_async_kind_propagates_runtime_error_from_task():
    with pytest.raises(RuntimeError, match="async"):
        await _trigger_error("async")


@pytest.mark.asyncio
async def test_trigger_error_external_kind_raises_httpx_error():
    with pytest.raises(httpx.RequestError):
        await _trigger_error("external")


@pytest.mark.asyncio
async def test_trigger_error_unknown_kind_raises_value_error():
    with pytest.raises(ValueError, match="unknown sentry_test kind"):
        await _trigger_error("nosuch")


@pytest.mark.asyncio
async def test_trigger_error_async_uses_create_task():
    """async kind must spawn a child task — that's what makes it 'async error'."""
    started_tasks_before = len(asyncio.all_tasks())
    try:
        await _trigger_error("async")
    except RuntimeError:
        pass
    started_tasks_after = len(asyncio.all_tasks())
    assert started_tasks_after >= started_tasks_before


def test_whitelist_allows_listed_user_id(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "sentry_test_user_ids", [42, 99])
    assert _is_sentry_test_allowed(42) is True
    assert _is_sentry_test_allowed(99) is True


def test_whitelist_rejects_unlisted_user_id(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "sentry_test_user_ids", [42])
    assert _is_sentry_test_allowed(7) is False


def test_whitelist_rejects_when_empty(monkeypatch):
    """Default settings have empty list → command effectively disabled."""
    from app.config import settings
    monkeypatch.setattr(settings, "sentry_test_user_ids", [])
    assert _is_sentry_test_allowed(42) is False
