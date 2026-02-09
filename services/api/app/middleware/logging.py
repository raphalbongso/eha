"""Structured logging middleware with PII redaction."""

import logging
import re
import time
import uuid
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# PII patterns to redact from logs
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# Match common name patterns (simple heuristic)
NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")


def redact_pii(text: str) -> str:
    """Redact email addresses and names from text."""
    text = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    return text


def setup_logging(debug: bool = False) -> None:
    """Configure structlog for JSON output."""
    log_level = logging.DEBUG if debug else logging.INFO

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs request/response with PII redaction."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        logger = structlog.get_logger()

        # Log request (redact path params that might contain PII)
        await logger.ainfo(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=redact_pii(str(request.url.path)),
            client=request.client.host if request.client else "unknown",
        )

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        await logger.ainfo(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=redact_pii(str(request.url.path)),
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        response.headers["X-Request-ID"] = request_id
        return response
