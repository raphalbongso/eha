"""Tests for WebSocket endpoint and connection manager."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from jose import jwt

from app.config import Settings
from app.routers.ws import _authenticate_ws
from app.services.ws_manager import ConnectionManager, publish_alert_sync


def _make_settings(**overrides) -> Settings:
    defaults = {
        "database_url": "postgresql+asyncpg://test:test@localhost/test",
        "redis_url": "redis://localhost:6379/0",
        "celery_broker_url": "redis://localhost:6379/1",
        "celery_result_backend": "redis://localhost:6379/2",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestAuthenticate:
    def test_valid_token(self):
        """Valid JWT with sub and type=access returns user_id."""
        settings = _make_settings()
        user_id = str(uuid.uuid4())
        token = jwt.encode(
            {"sub": user_id, "type": "access"},
            settings.jwt_private_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
        with patch("app.routers.ws.get_settings", return_value=settings):
            result = _authenticate_ws(token)
        assert result == uuid.UUID(user_id)

    def test_missing_type_raises(self):
        """Token without type=access is rejected."""
        settings = _make_settings()
        token = jwt.encode(
            {"sub": str(uuid.uuid4()), "type": "refresh"},
            settings.jwt_private_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
        with patch("app.routers.ws.get_settings", return_value=settings):
            with pytest.raises(ValueError, match="invalid token payload"):
                _authenticate_ws(token)

    def test_bad_token_raises(self):
        """Invalid JWT string is rejected."""
        settings = _make_settings()
        with patch("app.routers.ws.get_settings", return_value=settings):
            with pytest.raises(Exception):
                _authenticate_ws("not-a-jwt")


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        """Connect adds WS to tracking; disconnect removes it."""
        mgr = ConnectionManager()
        uid = uuid.uuid4()
        ws = MagicMock()
        ws.accept = MagicMock(return_value=_coro(None))
        ws.close = MagicMock(return_value=_coro(None))

        await mgr.connect(uid, ws)
        assert uid in mgr._connections
        assert ws in mgr._connections[uid]

        mgr.disconnect(uid, ws)
        assert uid not in mgr._connections

    @pytest.mark.asyncio
    async def test_send_to_user(self):
        """_send_to_user delivers JSON to all connected sockets."""
        mgr = ConnectionManager()
        uid = uuid.uuid4()
        ws = MagicMock()
        ws.accept = MagicMock(return_value=_coro(None))
        ws.send_json = MagicMock(return_value=_coro(None))

        await mgr.connect(uid, ws)
        await mgr._send_to_user(uid, {"type": "new_alert", "alert_id": "123"})

        ws.send_json.assert_called_once_with({"type": "new_alert", "alert_id": "123"})


class TestPublishAlertSync:
    def test_publishes_to_redis(self):
        """publish_alert_sync writes to Redis pub/sub channel."""
        mock_redis = MagicMock()
        with patch("app.services.ws_manager.redis.Redis.from_url", return_value=mock_redis), \
             patch("app.services.ws_manager.get_settings", return_value=_make_settings()):
            publish_alert_sync(
                user_id=str(uuid.uuid4()),
                payload={"type": "new_alert", "alert_id": "abc"},
            )
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "eha:ws:alerts"
        data = json.loads(call_args[0][1])
        assert data["payload"]["type"] == "new_alert"


# Helper for async mocks
async def _coro(value):
    return value
