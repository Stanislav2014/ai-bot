import logging
import logging.handlers
import sys
from pathlib import Path

import structlog

from app.config import settings


def setup_logging() -> None:
    level = logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if settings.log_file:
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        handlers.append(file_handler)

    # structlog already renders to JSON string; stdlib just passes message through
    passthrough = logging.Formatter("%(message)s")
    for h in handlers:
        h.setFormatter(passthrough)

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(level)
