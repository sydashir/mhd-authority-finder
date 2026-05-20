"""Structlog setup.

One entry point: :func:`configure`. Call once at process start. After that,
``structlog.get_logger(__name__)`` returns a bound logger anywhere in the app.
JSON is the only renderer — no human-friendly output mode by default, because
we want the same shape in dev, CI, and production.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from authority_finder.config import LogLevel


def configure(level: LogLevel = "INFO") -> None:
    """Wire structlog + the stdlib logging shim with a JSON renderer."""
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
