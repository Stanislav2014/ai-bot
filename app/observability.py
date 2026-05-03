import uuid

import sentry_sdk
import structlog


def new_trace_id() -> str:
    return uuid.uuid4().hex


def bind_request_context(
    *,
    trace_id: str,
    update_id: int | None = None,
    user_id: int | None = None,
    username: str | None = None,
) -> None:
    structlog.contextvars.clear_contextvars()
    bindings: dict[str, object] = {"trace_id": trace_id}
    if update_id is not None:
        bindings["update_id"] = update_id
    if user_id is not None:
        bindings["user_id"] = user_id
    structlog.contextvars.bind_contextvars(**bindings)

    for key, value in bindings.items():
        sentry_sdk.set_tag(key, value)

    if user_id is not None:
        user_payload: dict[str, object] = {"id": user_id}
        if username is not None:
            user_payload["username"] = username
        sentry_sdk.set_user(user_payload)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
    sentry_sdk.get_isolation_scope().clear()
