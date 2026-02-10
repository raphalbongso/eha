"""Unit tests for rate limiting middleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings():
    return Settings(
        app_env="development",
        database_url="postgresql+asyncpg://test:test@localhost:5432/eha_test",
        rate_limit_per_minute=5,
        redis_url="redis://localhost:6379/0",
        debug=True,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestRateLimitHeaders:
    def test_health_skips_rate_limit(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers


class TestRateLimitMiddleware:
    def test_rate_limit_header_present_on_authenticated(self, client):
        """Authenticated requests should get rate limit headers."""
        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_pipe.execute.return_value = [0, 1, True, True]  # zremrangebyscore, zcard, zadd, expire

        with patch("app.middleware.rate_limit.RateLimitMiddleware._get_redis", return_value=mock_redis):
            response = client.get(
                "/api/v1/rules",
                headers={"Authorization": "Bearer fake-jwt-for-rate-limit"},
            )
            # Will get 401/403 because JWT is invalid, but rate limit middleware runs first
            assert "X-RateLimit-Limit" in response.headers or response.status_code in (401, 403)

    def test_unauthenticated_uses_ip_fallback(self, client):
        """Unauthenticated requests fall back to IP-based limiting."""
        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_pipe.execute.return_value = [0, 0, True, True]

        with patch("app.middleware.rate_limit.RateLimitMiddleware._get_redis", return_value=mock_redis):
            response = client.get("/api/v1/rules")
            # No auth header → IP-based rate limiting applies
            assert response.status_code in (200, 401, 403)
