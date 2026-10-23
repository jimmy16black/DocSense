import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# Context variables for tracing
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


def add_correlation_context(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    cid = correlation_id_ctx.get()
    if cid:
        event_dict["correlation_id"] = cid

    uid = user_id_ctx.get()
    if uid:
        event_dict["user_id"] = uid

    return event_dict


def setup_logging(debug: bool = False) -> None:
    log_level = logging.DEBUG if debug else logging.INFO

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        add_correlation_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str = "docsense") -> Any:
    return structlog.get_logger(name)
