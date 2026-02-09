"""Unit tests for auth router (JWT creation, refresh, PKCE state)."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.config import Settings
from app.main import create_app
from app.routers.auth import _create_jwt


@pytest.fixture
def settings():
    return Settings(
        app_env="development",
        database_url="postgresql+asyncpg://test:test@localhost:5432/eha_test",
        jwt_private_key="test-secret-key-for-jwt-signing",
        jwt_algorithm="HS256",
        jwt_access_token_ttl_minutes=15,
        jwt_refresh_token_ttl_days=7,
        redis_url="redis://localhost:6379/0",
        debug=True,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestCreateJWT:
    def test_access_token_contains_correct_claims(self, settings):
        token = _create_jwt("user-123", "access", settings, timedelta(minutes=15))
        payload = jwt.decode(token, "test-secret-key-for-jwt-signing", algorithms=["HS256"])

        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_refresh_token_type(self, settings):
        token = _create_jwt("user-123", "refresh", settings, timedelta(days=7))
        payload = jwt.decode(token, "test-secret-key-for-jwt-signing", algorithms=["HS256"])
        assert payload["type"] == "refresh"

    def test_token_expires_correctly(self, settings):
        token = _create_jwt("user-123", "access", settings, timedelta(minutes=15))
        payload = jwt.decode(token, "test-secret-key-for-jwt-signing", algorithms=["HS256"])
        iat = payload["iat"]
        exp = payload["exp"]
        assert (exp - iat) == 15 * 60


class TestRefreshEndpoint:
    def test_valid_refresh(self, client, settings):
        refresh = _create_jwt("user-123", "refresh", settings, timedelta(days=7))
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["expires_in"] == 15 * 60

    def test_access_token_cannot_refresh(self, client, settings):
        access = _create_jwt("user-123", "access", settings, timedelta(minutes=15))
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client):
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid.jwt.token"})
        assert response.status_code == 401

    def test_expired_refresh_returns_401(self, client, settings):
        expired = _create_jwt("user-123", "refresh", settings, timedelta(seconds=-1))
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": expired})
        assert response.status_code == 401


class TestPKCEStateStore:
    @pytest.mark.asyncio
    async def test_store_and_pop(self, settings):
        """Test Redis-backed PKCE state store/pop cycle."""
        from app.routers.auth import _pop_pkce_state, _store_pkce_state

        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline

        stored_data = {"code_verifier": "test-verifier", "created_at": "2024-01-01T00:00:00"}
        mock_pipeline.execute.return_value = [json.dumps(stored_data), 1]

        with patch("app.routers.auth._get_redis", return_value=mock_redis):
            await _store_pkce_state("test-state", stored_data, settings)
            mock_redis.set.assert_called_once()

            result = await _pop_pkce_state("test-state", settings)
            assert result == stored_data

    @pytest.mark.asyncio
    async def test_pop_missing_state_returns_none(self, settings):
        from app.routers.auth import _pop_pkce_state

        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [None, 0]

        with patch("app.routers.auth._get_redis", return_value=mock_redis):
            result = await _pop_pkce_state("nonexistent", settings)
            assert result is None


class TestMeEndpointUnauthorized:
    def test_me_without_auth(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code in (401, 403)
