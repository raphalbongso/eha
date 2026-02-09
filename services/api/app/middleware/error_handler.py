"""Global error handling middleware."""

import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.logging import redact_pii

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and return safe error responses."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            # Redact PII from error messages before logging
            error_msg = redact_pii(str(exc))
            tb = traceback.format_exc()

            logger.error(
                "Unhandled exception: %s\n%s",
                error_msg,
                redact_pii(tb),
            )

            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An internal error occurred. Please try again later.",
                    "error_type": type(exc).__name__,
                },
            )
