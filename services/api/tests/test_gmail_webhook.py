"""Integration test for Gmail webhook flow (mocked Gmail API)."""

import base64
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings():
    """Test settings."""
    return Settings(
        app_env="development",
        database_url="postgresql+asyncpg://test:test@localhost:5432/eha_test",
        google_pubsub_verification_token="test-token",
        debug=True,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestGmailWebhook:
    def test_webhook_valid_notification(self, client):
        """Test that a valid Pub/Sub notification is accepted and task enqueued."""
        notification_data = {
            "emailAddress": "user@gmail.com",
            "historyId": "12345",
        }
        encoded_data = base64.b64encode(json.dumps(notification_data).encode()).decode()

        payload = {
            "message": {
                "data": encoded_data,
                "messageId": "pubsub-msg-1",
                "publishTime": "2024-02-01T00:00:00Z",
            },
            "subscription": "projects/my-project/subscriptions/gmail-push",
        }

        with patch("app.routers.gmail._verify_pubsub_token", return_value={"verified": True}):
            with patch("app.tasks.gmail_tasks.process_gmail_notification.delay") as mock_task:
                response = client.post("/api/v1/gmail/webhook", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_task.assert_called_once_with(
            email_address="user@gmail.com",
            history_id="12345",
        )

    def test_webhook_empty_message(self, client):
        """Test that empty Pub/Sub message is handled gracefully."""
        payload = {
            "message": {"data": "", "messageId": "pubsub-msg-2"},
            "subscription": "projects/my-project/subscriptions/gmail-push",
        }

        with patch("app.routers.gmail._verify_pubsub_token", return_value={"verified": True}):
            response = client.post("/api/v1/gmail/webhook", json=payload)

        assert response.status_code == 200
        assert "empty" in response.json().get("detail", "")

    def test_webhook_invalid_json_data(self, client):
        """Test that invalid base64 data is handled gracefully."""
        payload = {
            "message": {
                "data": base64.b64encode(b"not json").decode(),
                "messageId": "pubsub-msg-3",
            },
            "subscription": "projects/my-project/subscriptions/gmail-push",
        }

        with patch("app.routers.gmail._verify_pubsub_token", return_value={"verified": True}):
            response = client.post("/api/v1/gmail/webhook", json=payload)

        assert response.status_code == 200
        assert "invalid" in response.json().get("detail", "")

    def test_webhook_missing_fields(self, client):
        """Test notification missing emailAddress or historyId."""
        notification_data = {"emailAddress": "user@gmail.com"}  # missing historyId
        encoded_data = base64.b64encode(json.dumps(notification_data).encode()).decode()

        payload = {
            "message": {"data": encoded_data, "messageId": "pubsub-msg-4"},
            "subscription": "test",
        }

        with patch("app.routers.gmail._verify_pubsub_token", return_value={"verified": True}):
            response = client.post("/api/v1/gmail/webhook", json=payload)

        assert response.status_code == 200
        assert "missing" in response.json().get("detail", "")


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "eha-api"
