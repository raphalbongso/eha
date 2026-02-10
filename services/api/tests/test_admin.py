"""Tests for admin routes: data export endpoint."""

import json
import uuid
from datetime import datetime, date, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.admin import router, _serialize_row

TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

EXPECTED_EXPORT_KEYS = {
    "exported_at",
    "user",
    "rules",
    "alerts",
    "drafts",
    "processed_messages",
    "proposed_events",
    "user_preferences",
    "follow_up_reminders",
    "digest_subscriptions",
    "slack_configs",
    "audit_log",
}


def _override_user_id():
    return TEST_USER_ID


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    return AsyncMock()


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


@pytest.fixture
def unauthed_app(mock_db):
    """App without auth override — requires real JWT."""
    from app.dependencies import get_db

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    async def _get_db():
        yield mock_db

    test_app.dependency_overrides[get_db] = _get_db
    return test_app


@pytest.fixture
def unauthed_client(unauthed_app):
    return TestClient(unauthed_app)


def _make_user_row():
    """Create a mock User SQLAlchemy object with realistic column mapper."""
    user = MagicMock()
    user.id = TEST_USER_ID
    user.google_id = "google-123"
    user.email = "test@example.com"
    user.name = "Test User"
    user.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)

    # Set up __mapper__.columns to match User model
    cols = []
    for key in ("id", "google_id", "email", "name", "created_at", "updated_at"):
        col = MagicMock()
        col.key = key
        cols.append(col)
    type(user).__mapper__ = MagicMock()
    type(user).__mapper__.columns = cols
    return user


def _make_rule_row():
    rule = MagicMock()
    rule.id = uuid.uuid4()
    rule.user_id = TEST_USER_ID
    rule.name = "Urgent emails"
    rule.conditions = {"logic": "AND", "conditions": []}
    rule.is_active = True
    rule.created_at = datetime(2025, 2, 1, tzinfo=timezone.utc)
    rule.updated_at = datetime(2025, 2, 1, tzinfo=timezone.utc)

    cols = []
    for key in ("id", "user_id", "name", "conditions", "is_active", "created_at", "updated_at"):
        col = MagicMock()
        col.key = key
        cols.append(col)
    type(rule).__mapper__ = MagicMock()
    type(rule).__mapper__.columns = cols
    return rule


def _setup_mock_db(mock_db, user_row, extra_rows=None):
    """Configure mock_db.execute to return user_row for the first call,
    then empty results for subsequent model queries, plus flush/add for audit.

    extra_rows: dict mapping call index -> list of row objects to return.
    """
    if extra_rows is None:
        extra_rows = {}

    call_count = 0

    async def _execute(stmt):
        nonlocal call_count
        idx = call_count
        call_count += 1

        result = MagicMock()
        if idx == 0:
            # First call: select(User)
            result.scalar_one_or_none.return_value = user_row
        else:
            # Subsequent calls: select(Model).where(...)
            rows = extra_rows.get(idx, [])
            result.scalars.return_value.all.return_value = rows
        return result

    mock_db.execute = AsyncMock(side_effect=_execute)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExportUserData:

    def test_export_returns_200_with_correct_headers(self, client, mock_db):
        user = _make_user_row()
        _setup_mock_db(mock_db, user)

        resp = client.get("/api/v1/users/me/export")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        assert "attachment" in resp.headers["content-disposition"]
        assert "eha-data-export-" in resp.headers["content-disposition"]
        assert date.today().isoformat() in resp.headers["content-disposition"]

    def test_export_contains_all_expected_keys(self, client, mock_db):
        user = _make_user_row()
        _setup_mock_db(mock_db, user)

        resp = client.get("/api/v1/users/me/export")
        data = resp.json()

        assert set(data.keys()) == EXPECTED_EXPORT_KEYS

    def test_export_user_profile_data(self, client, mock_db):
        user = _make_user_row()
        _setup_mock_db(mock_db, user)

        resp = client.get("/api/v1/users/me/export")
        data = resp.json()

        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["name"] == "Test User"
        assert data["user"]["id"] == str(TEST_USER_ID)

    def test_export_includes_rules(self, client, mock_db):
        user = _make_user_row()
        rule = _make_rule_row()
        # rules is call index 1 (after the user query)
        _setup_mock_db(mock_db, user, extra_rows={1: [rule]})

        resp = client.get("/api/v1/users/me/export")
        data = resp.json()

        assert len(data["rules"]) == 1
        assert data["rules"][0]["name"] == "Urgent emails"

    def test_export_empty_collections(self, client, mock_db):
        user = _make_user_row()
        _setup_mock_db(mock_db, user)

        resp = client.get("/api/v1/users/me/export")
        data = resp.json()

        for key in EXPECTED_EXPORT_KEYS - {"exported_at", "user"}:
            assert isinstance(data[key], list)

    def test_export_has_exported_at_timestamp(self, client, mock_db):
        user = _make_user_row()
        _setup_mock_db(mock_db, user)

        resp = client.get("/api/v1/users/me/export")
        data = resp.json()

        assert data["exported_at"].endswith("Z")
        # Should be a valid ISO timestamp
        datetime.fromisoformat(data["exported_at"].rstrip("Z"))

    def test_export_writes_audit_log(self, client, mock_db):
        user = _make_user_row()
        _setup_mock_db(mock_db, user)

        resp = client.get("/api/v1/users/me/export")
        assert resp.status_code == 200

        # write_audit_log calls db.add then db.flush
        mock_db.add.assert_called_once()
        audit_entry = mock_db.add.call_args[0][0]
        assert audit_entry.action == "user.data_exported"
        assert audit_entry.entity_type == "user"
        assert audit_entry.user_id == TEST_USER_ID

    def test_export_user_not_found_returns_404(self, client, mock_db):
        _setup_mock_db(mock_db, None)

        resp = client.get("/api/v1/users/me/export")
        assert resp.status_code == 404


class TestExportRequiresAuth:

    def test_export_no_token_returns_401(self, unauthed_client):
        resp = unauthed_client.get("/api/v1/users/me/export")
        assert resp.status_code in (401, 403)


class TestSerializeRow:

    def test_uuid_converted_to_string(self):
        obj = MagicMock()
        uid = uuid.uuid4()
        obj.id = uid
        col = MagicMock()
        col.key = "id"
        type(obj).__mapper__ = MagicMock()
        type(obj).__mapper__.columns = [col]

        result = _serialize_row(obj)
        assert result["id"] == str(uid)

    def test_datetime_converted_to_isoformat(self):
        obj = MagicMock()
        dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        obj.created_at = dt
        col = MagicMock()
        col.key = "created_at"
        type(obj).__mapper__ = MagicMock()
        type(obj).__mapper__.columns = [col]

        result = _serialize_row(obj)
        assert result["created_at"] == dt.isoformat()

    def test_bytes_columns_skipped(self):
        obj = MagicMock()
        obj.webhook_url = b"encrypted-data"
        obj.name = "test"
        cols = []
        for key in ("webhook_url", "name"):
            col = MagicMock()
            col.key = key
            cols.append(col)
        type(obj).__mapper__ = MagicMock()
        type(obj).__mapper__.columns = cols

        result = _serialize_row(obj)
        assert "webhook_url" not in result
        assert result["name"] == "test"

    def test_enum_converted_to_value(self):
        import enum

        class Status(str, enum.Enum):
            ACTIVE = "active"

        obj = MagicMock()
        obj.status = Status.ACTIVE
        col = MagicMock()
        col.key = "status"
        type(obj).__mapper__ = MagicMock()
        type(obj).__mapper__.columns = [col]

        result = _serialize_row(obj)
        assert result["status"] == "active"

    def test_jsonb_passed_through(self):
        obj = MagicMock()
        obj.conditions = {"logic": "AND", "conditions": [{"type": "from_contains", "value": "boss"}]}
        col = MagicMock()
        col.key = "conditions"
        type(obj).__mapper__ = MagicMock()
        type(obj).__mapper__.columns = [col]

        result = _serialize_row(obj)
        assert result["conditions"] == obj.conditions
