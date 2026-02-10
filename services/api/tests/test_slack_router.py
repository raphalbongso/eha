"""Unit tests for the Slack router endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.slack import router

# ---------------------------------------------------------------------------
# Test app setup
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _override_user_id():
    return TEST_USER_ID


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
def app(mock_db):
    from app.dependencies import get_current_user_id, get_db

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    test_app.dependency_overrides[get_current_user_id] = _override_user_id

    async def _get_db():
        yield mock_db

    test_app.dependency_overrides[get_db] = _get_db
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


def _make_config_row(is_enabled=True, types=None):
    cfg = MagicMock()
    cfg.user_id = TEST_USER_ID
    cfg.webhook_url = b"encrypted-webhook"
    cfg.is_enabled = is_enabled
    cfg.enabled_notification_types = types or []
    cfg.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return cfg


# ---------------------------------------------------------------------------
# GET /slack/config
# ---------------------------------------------------------------------------


class TestGetSlackConfig:

    def test_returns_config(self, client, mock_db):
        config = _make_config_row()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = config
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.routers.slack.get_crypto_service") as mock_crypto, \
             patch("app.routers.slack.get_settings"):
            mock_crypto.return_value.decrypt.return_value = "https://hooks.slack.com/services/T00/B00/abcdef"
            resp = client.get("/api/v1/slack/config")

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_enabled"] is True
        assert data["webhook_url_masked"] == "****abcdef"
        assert data["enabled_notification_types"] == []

    def test_returns_404_when_no_config(self, client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.routers.slack.get_settings"):
            resp = client.get("/api/v1/slack/config")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /slack/config
# ---------------------------------------------------------------------------


class TestUpdateSlackConfig:

    def test_create_new_config(self, client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None  # no existing config
        mock_db.execute = AsyncMock(return_value=result_mock)

        def _set_created_at(obj):
            obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        mock_db.add = MagicMock(side_effect=_set_created_at)
        mock_db.flush = AsyncMock()

        with patch("app.routers.slack.get_crypto_service") as mock_crypto, \
             patch("app.routers.slack.get_settings"):
            mock_crypto.return_value.encrypt.return_value = b"encrypted"
            mock_crypto.return_value.decrypt.return_value = "https://hooks.slack.com/services/T00/B00/newurl"

            resp = client.put("/api/v1/slack/config", json={
                "webhook_url": "https://hooks.slack.com/services/T00/B00/newurl",
                "is_enabled": True,
                "enabled_notification_types": ["RULE_MATCH"],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_enabled"] is True
        assert data["webhook_url_masked"] == "****newurl"
        assert data["enabled_notification_types"] == ["RULE_MATCH"]
        mock_db.add.assert_called_once()

    def test_update_existing_config(self, client, mock_db):
        existing = _make_config_row()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=result_mock)
        mock_db.flush = AsyncMock()

        with patch("app.routers.slack.get_crypto_service") as mock_crypto, \
             patch("app.routers.slack.get_settings"):
            mock_crypto.return_value.encrypt.return_value = b"new-encrypted"
            mock_crypto.return_value.decrypt.return_value = "https://hooks.slack.com/services/T00/B00/update"

            resp = client.put("/api/v1/slack/config", json={
                "webhook_url": "https://hooks.slack.com/services/T00/B00/update",
                "is_enabled": False,
                "enabled_notification_types": [],
            })

        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is False

    def test_create_without_webhook_url_returns_400(self, client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.routers.slack.get_crypto_service"), \
             patch("app.routers.slack.get_settings"):
            resp = client.put("/api/v1/slack/config", json={
                "is_enabled": True,
            })

        assert resp.status_code == 400

    def test_invalid_webhook_url_returns_422(self, client, mock_db):
        resp = client.put("/api/v1/slack/config", json={
            "webhook_url": "https://example.com/not-slack",
        })
        assert resp.status_code == 422

    def test_invalid_notification_type_returns_422(self, client, mock_db):
        resp = client.put("/api/v1/slack/config", json={
            "webhook_url": "https://hooks.slack.com/services/T00/B00/x",
            "enabled_notification_types": ["INVALID_TYPE"],
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /slack/test
# ---------------------------------------------------------------------------


class TestTestSlackNotification:

    def test_sends_test_notification(self, client, mock_db):
        config = _make_config_row()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = config
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.routers.slack.get_crypto_service") as mock_crypto, \
             patch("app.routers.slack.get_slack_service") as mock_slack_svc, \
             patch("app.routers.slack.get_settings"):
            mock_crypto.return_value.decrypt.return_value = "https://hooks.slack.com/services/T00/B00/test"
            mock_slack_svc.return_value.send = AsyncMock(return_value=True)

            resp = client.post("/api/v1/slack/test")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_test_returns_failure(self, client, mock_db):
        config = _make_config_row()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = config
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.routers.slack.get_crypto_service") as mock_crypto, \
             patch("app.routers.slack.get_slack_service") as mock_slack_svc, \
             patch("app.routers.slack.get_settings"):
            mock_crypto.return_value.decrypt.return_value = "https://hooks.slack.com/services/T00/B00/test"
            mock_slack_svc.return_value.send = AsyncMock(return_value=False)

            resp = client.post("/api/v1/slack/test")

        data = resp.json()
        assert data["success"] is False

    def test_returns_404_when_no_config(self, client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.routers.slack.get_settings"):
            resp = client.post("/api/v1/slack/test")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /slack/config
# ---------------------------------------------------------------------------


class TestDeleteSlackConfig:

    def test_deletes_config(self, client, mock_db):
        config = _make_config_row()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = config
        mock_db.execute = AsyncMock(return_value=result_mock)
        mock_db.delete = AsyncMock()
        mock_db.flush = AsyncMock()

        resp = client.delete("/api/v1/slack/config")

        assert resp.status_code == 204
        mock_db.delete.assert_called_once_with(config)

    def test_returns_404_when_no_config(self, client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        resp = client.delete("/api/v1/slack/config")

        assert resp.status_code == 404
