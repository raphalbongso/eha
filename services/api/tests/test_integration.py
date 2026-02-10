"""Integration tests: API app creation, middleware stack, endpoint routing."""

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
        redis_url="redis://localhost:6379/0",
        debug=True,
    )


@pytest.fixture
def production_settings():
    return Settings(
        app_env="production",
        database_url="postgresql+asyncpg://test:test@localhost:5432/eha_test",
        redis_url="redis://localhost:6379/0",
        debug=False,
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


class TestAppFactory:
    def test_app_creates_successfully(self, settings):
        app = create_app(settings)
        assert app.title == "EHA - Email Helper Agent"
        assert app.version == "1.0.0"

    def test_docs_available_in_dev(self, settings):
        app = create_app(settings)
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

    def test_docs_disabled_in_production(self, production_settings):
        app = create_app(production_settings)
        assert app.docs_url is None
        assert app.redoc_url is None


class TestHealthEndpoints:
    def test_basic_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "eha-api"

    def test_metrics_endpoint(self, client):
        # Hit a non-excluded endpoint first to generate HTTP metrics
        client.get("/health")
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        body = response.text
        assert "http_request_duration" in body


class TestCORSHeaders:
    def test_cors_preflight(self, client):
        response = client.options(
            "/api/v1/rules",
            headers={
                "Origin": "http://localhost:19006",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_cors_disallowed_origin(self, client):
        response = client.options(
            "/api/v1/rules",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") != "http://evil.example.com"


class TestRouterRegistration:
    def test_auth_routes_registered(self, client):
        """Verify auth router is registered by hitting a known endpoint."""
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid"})
        assert response.status_code in (401, 422)  # Not 404

    def test_rules_routes_registered(self, client):
        response = client.get("/api/v1/rules", headers={"Authorization": "Bearer fake"})
        assert response.status_code in (401, 403)  # Not 404

    def test_alerts_routes_registered(self, client):
        response = client.get("/api/v1/alerts", headers={"Authorization": "Bearer fake"})
        assert response.status_code in (401, 403)

    def test_gmail_webhook_registered(self, client):
        response = client.post("/api/v1/gmail/webhook", json={})
        assert response.status_code != 404

    def test_nonexistent_route_returns_404(self, client):
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404


class TestInputValidation:
    def test_rules_create_name_too_long(self, authed_client):
        response = authed_client.post(
            "/api/v1/rules",
            json={
                "name": "x" * 256,
                "conditions": {"logic": "AND", "conditions": [{"type": "from_contains", "value": "test"}]},
            },
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code == 422

    def test_rules_create_empty_name(self, authed_client):
        response = authed_client.post(
            "/api/v1/rules",
            json={
                "name": "",
                "conditions": {"logic": "AND", "conditions": [{"type": "from_contains", "value": "test"}]},
            },
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code == 422

    def test_rules_create_too_many_conditions(self, authed_client):
        conditions = [{"type": "from_contains", "value": f"test{i}"} for i in range(21)]
        response = authed_client.post(
            "/api/v1/rules",
            json={
                "name": "test",
                "conditions": {"logic": "AND", "conditions": conditions},
            },
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code == 422
