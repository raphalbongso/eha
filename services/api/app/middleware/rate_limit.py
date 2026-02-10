"""Per-user rate limiting middleware using Redis sliding window."""

import logging
import time
from typing import Callable

import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import Settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter per authenticated user."""

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._max_requests = settings.rate_limit_per_minute
        self._window_seconds = 60
        self._redis: redis.Redis | None = None
        self._redis_url = settings.redis_url

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def _extract_user_identifier(self, request: Request) -> str | None:
        """Extract user identifier from Authorization header for rate limiting."""
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            # Use token hash as identifier (don't store full token)
            import hashlib

            token = auth[7:]
            return hashlib.sha256(token.encode()).hexdigest()[:16]
        # Fall back to IP for unauthenticated requests
        if request.client:
            return f"ip:{request.client.host}"
        return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        identifier = self._extract_user_identifier(request)
        if not identifier:
            return await call_next(request)

        try:
            r = await self._get_redis()
            key = f"ratelimit:{identifier}"
            now = time.time()
            window_start = now - self._window_seconds

            pipe = r.pipeline()
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            # Count requests in window
            pipe.zcard(key)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Set TTL on the key
            pipe.expire(key, self._window_seconds)
            results = await pipe.execute()

            request_count = results[1]

            if request_count >= self._max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={
                        "Retry-After": str(self._window_seconds),
                        "X-RateLimit-Limit": str(self._max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self._max_requests)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self._max_requests - request_count - 1))
            return response

        except Exception as e:
            # If Redis is down, allow the request (fail open)
            logger.warning("Rate limit Redis error: %s", e)
            return await call_next(request)
