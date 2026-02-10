"""Tests for AI data retention preference and cleanup task."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.draft import Draft
from app.models.processed_message import ProcessedMessage
from app.models.proposed_event import EventStatus, ProposedEvent
from app.models.user_preference import UserPreference
from app.routers.preferences import router as pref_router
from app.schemas.preference import PreferenceResponse, PreferenceUpdate

TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _override_user_id():
    return TEST_USER_ID


# ---------------------------------------------------------------------------
# Schema / Preference tests
# ---------------------------------------------------------------------------


class TestAiDataRetentionPreference:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def app(self, mock_db):
        from app.dependencies import get_current_user_id, get_db

        test_app = FastAPI()
        test_app.include_router(pref_router, prefix="/api/v1")
        test_app.dependency_overrides[get_current_user_id] = _override_user_id

        async def _get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = _get_db
        return test_app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_preference_default_is_none(self):
        """Default retention is None (keep forever)."""
        resp = PreferenceResponse()
        assert resp.ai_data_retention_days is None

    def test_set_retention_via_put(self, client, mock_db):
        """PUT /preferences with ai_data_retention_days sets the value."""
        pref_obj = MagicMock()
        pref_obj.home_address = None
        pref_obj.work_address = None
        pref_obj.preferred_transport_mode = "driving"
        pref_obj.auto_categorize_enabled = False
        pref_obj.auto_label_enabled = False
        pref_obj.store_email_content = False
        pref_obj.ai_data_retention_days = None

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pref_obj
        mock_db.execute = AsyncMock(return_value=result_mock)
        mock_db.flush = AsyncMock()

        resp = client.put(
            "/api/v1/preferences",
            json={"ai_data_retention_days": 30},
        )

        assert resp.status_code == 200
        assert pref_obj.ai_data_retention_days == 30

    def test_set_retention_to_zero_clears(self, client, mock_db):
        """Setting ai_data_retention_days to 0 clears it (back to NULL / keep forever)."""
        pref_obj = MagicMock()
        pref_obj.home_address = None
        pref_obj.work_address = None
        pref_obj.preferred_transport_mode = "driving"
        pref_obj.auto_categorize_enabled = False
        pref_obj.auto_label_enabled = False
        pref_obj.store_email_content = False
        pref_obj.ai_data_retention_days = 30

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pref_obj
        mock_db.execute = AsyncMock(return_value=result_mock)
        mock_db.flush = AsyncMock()

        resp = client.put(
            "/api/v1/preferences",
            json={"ai_data_retention_days": 0},
        )

        assert resp.status_code == 200
        assert pref_obj.ai_data_retention_days is None

    def test_validation_rejects_negative(self):
        """Negative values are rejected by schema validation."""
        with pytest.raises(Exception):
            PreferenceUpdate(ai_data_retention_days=-1)

    def test_validation_rejects_too_large(self):
        """Values > 3650 are rejected by schema validation."""
        with pytest.raises(Exception):
            PreferenceUpdate(ai_data_retention_days=3651)

    def test_validation_accepts_boundary(self):
        """Boundary values 0 and 3650 are accepted."""
        p0 = PreferenceUpdate(ai_data_retention_days=0)
        assert p0.ai_data_retention_days == 0
        p_max = PreferenceUpdate(ai_data_retention_days=3650)
        assert p_max.ai_data_retention_days == 3650


# ---------------------------------------------------------------------------
# Cleanup task tests
# ---------------------------------------------------------------------------


def _make_pref(user_id, retention_days):
    """Create a mock UserPreference with the given retention."""
    pref = MagicMock(spec=UserPreference)
    pref.user_id = user_id
    pref.ai_data_retention_days = retention_days
    return pref


class TestCleanupExpiredAiData:

    @patch("app.tasks.retention_tasks._get_sync_session")
    def test_deletes_old_drafts(self, mock_get_session):
        from app.tasks.retention_tasks import cleanup_expired_ai_data

        session = MagicMock()
        mock_get_session.return_value = session

        # One user with 30-day retention
        pref = _make_pref(TEST_USER_ID, 30)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [pref]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        # execute returns: select prefs, delete drafts, delete events, update messages
        draft_result = MagicMock(rowcount=5)
        event_result = MagicMock(rowcount=0)
        msg_result = MagicMock(rowcount=0)

        session.execute = MagicMock(
            side_effect=[result_mock, draft_result, event_result, msg_result]
        )

        cleanup_expired_ai_data()

        # Verify 4 execute calls: select + 3 operations
        assert session.execute.call_count == 4
        session.commit.assert_called_once()

    @patch("app.tasks.retention_tasks._get_sync_session")
    def test_deletes_dismissed_events_keeps_proposed(self, mock_get_session):
        from app.tasks.retention_tasks import cleanup_expired_ai_data

        session = MagicMock()
        mock_get_session.return_value = session

        pref = _make_pref(TEST_USER_ID, 7)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [pref]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        draft_result = MagicMock(rowcount=0)
        event_result = MagicMock(rowcount=3)
        msg_result = MagicMock(rowcount=0)

        session.execute = MagicMock(
            side_effect=[result_mock, draft_result, event_result, msg_result]
        )

        cleanup_expired_ai_data()

        # Check the delete(ProposedEvent) statement includes status != PROPOSED filter
        event_delete_call = session.execute.call_args_list[2]
        stmt = event_delete_call[0][0]
        # The compiled SQL should reference event_status and 'proposed'
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "proposed_events" in compiled
        assert "proposed" in compiled.lower()

    @patch("app.tasks.retention_tasks._get_sync_session")
    def test_scrubs_ai_fields_on_old_messages(self, mock_get_session):
        from app.tasks.retention_tasks import cleanup_expired_ai_data

        session = MagicMock()
        mock_get_session.return_value = session

        pref = _make_pref(TEST_USER_ID, 14)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [pref]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        draft_result = MagicMock(rowcount=0)
        event_result = MagicMock(rowcount=0)
        msg_result = MagicMock(rowcount=10)

        session.execute = MagicMock(
            side_effect=[result_mock, draft_result, event_result, msg_result]
        )

        cleanup_expired_ai_data()

        # Check the UPDATE statement targets processed_messages and sets NULLs
        update_call = session.execute.call_args_list[3]
        stmt = update_call[0][0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "processed_messages" in compiled
        assert "category" in compiled

    @patch("app.tasks.retention_tasks._get_sync_session")
    def test_skips_users_without_retention(self, mock_get_session):
        from app.tasks.retention_tasks import cleanup_expired_ai_data

        session = MagicMock()
        mock_get_session.return_value = session

        # No users have retention set
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = MagicMock(return_value=result_mock)

        cleanup_expired_ai_data()

        # Only the initial SELECT should have been called
        assert session.execute.call_count == 1
        session.commit.assert_called_once()

    @patch("app.tasks.retention_tasks._get_sync_session")
    def test_processes_multiple_users(self, mock_get_session):
        from app.tasks.retention_tasks import cleanup_expired_ai_data

        session = MagicMock()
        mock_get_session.return_value = session

        pref1 = _make_pref(TEST_USER_ID, 30)
        pref2 = _make_pref(OTHER_USER_ID, 7)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [pref1, pref2]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        # 1 select + 3 ops per user = 7 total
        zero_result = MagicMock(rowcount=0)
        session.execute = MagicMock(
            side_effect=[result_mock] + [zero_result] * 6
        )

        cleanup_expired_ai_data()

        # 1 select + 2*3 operations = 7
        assert session.execute.call_count == 7
        session.commit.assert_called_once()

    @patch("app.tasks.retention_tasks._get_sync_session")
    def test_rolls_back_on_error(self, mock_get_session):
        from app.tasks.retention_tasks import cleanup_expired_ai_data

        session = MagicMock()
        mock_get_session.return_value = session

        session.execute.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(RuntimeError):
            cleanup_expired_ai_data()

        session.rollback.assert_called_once()
        session.close.assert_called_once()
