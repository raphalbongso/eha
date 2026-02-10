"""Tests for alerts router edge cases and validation."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_current_user_id
from app.main import create_app

FAKE_USER_ID = uuid.uuid4()


@pytest.fixture
def settings():
    return Settings(
        app_env="development",
        database_url="postgresql+asyncpg://test:test@localhost:5432/eha_test",
        debug=True,
    )


@pytest.fixture
def app(settings):
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return app


@pytest.fixture
def authed_app(app):
    app.dependency_overrides[get_current_user_id] = lambda: FAKE_USER_ID
    yield app
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def authed_client(authed_app):
    return TestClient(authed_app)


class TestAlertsEndpoint:
    def test_alerts_requires_auth(self, client):
        response = client.get("/api/v1/alerts")
        assert response.status_code in (401, 403)

    def test_mark_read_requires_auth(self, client):
        response = client.post("/api/v1/alerts/mark-read", json={"alert_ids": ["some-id"]})
        assert response.status_code in (401, 403)

    def test_mark_read_empty_list_rejected(self, authed_client):
        """Empty alert_ids list should be rejected by validation."""
        response = authed_client.post(
            "/api/v1/alerts/mark-read",
            json={"alert_ids": []},
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code == 422


class TestQueryParameters:
    def test_alerts_limit_max(self, authed_client):
        """Limit parameter has max_length=200."""
        response = authed_client.get(
            "/api/v1/alerts?limit=201",
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code == 422

    def test_alerts_negative_offset_rejected(self, authed_client):
        response = authed_client.get(
            "/api/v1/alerts?offset=-1",
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code == 422
