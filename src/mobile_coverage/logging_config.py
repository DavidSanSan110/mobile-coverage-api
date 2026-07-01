import logging
from typing import Any

import structlog


def configure_logging(log_format: str) -> None:
    """Configure structlog processors based on LOG_FORMAT env var.

    'console' produces human-readable coloured output for local development.
    'json' produces one JSON object per line for log aggregators in production.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "json":
        final: Any = structlog.processors.JSONRenderer()
    else:
        final = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, final],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
