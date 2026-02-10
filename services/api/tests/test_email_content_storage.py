"""Tests for optional email content storage (user opt-in, encrypted)."""

import uuid
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.preferences import router as pref_router
from app.schemas.preference import PreferenceResponse
from app.tasks.gmail_tasks import _process_single_message

TEST_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _override_user_id():
    return TEST_USER_ID


# ---------------------------------------------------------------------------
# Preference tests
# ---------------------------------------------------------------------------


class TestStoreEmailContentPreference:

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

    def test_preference_default_is_false(self):
        resp = PreferenceResponse()
        assert resp.store_email_content is False

    def test_toggle_store_email_content_via_put(self, client, mock_db):
        """PUT /preferences with store_email_content=true updates the preference."""
        # Mock: no existing preference row
        pref_obj = MagicMock()
        pref_obj.home_address = None
        pref_obj.work_address = None
        pref_obj.preferred_transport_mode = "driving"
        pref_obj.auto_categorize_enabled = False
        pref_obj.auto_label_enabled = False
        pref_obj.store_email_content = False

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pref_obj
        mock_db.execute = AsyncMock(return_value=result_mock)
        mock_db.flush = AsyncMock()

        resp = client.put(
            "/api/v1/preferences",
            json={"store_email_content": True},
        )

        assert resp.status_code == 200
        # The mock pref should have been updated
        assert pref_obj.store_email_content is True


# ---------------------------------------------------------------------------
# Gmail task content storage tests
# ---------------------------------------------------------------------------


class TestProcessSingleMessageContentStorage:

    def _make_parsed(self, body_text="Hello world", body_html="<p>Hello</p>"):
        parsed = MagicMock()
        parsed.message_id = "msg_test_001"
        parsed.thread_id = "thread_001"
        parsed.subject = "Test Subject"
        parsed.from_addr = "alice@example.com"
        parsed.snippet = "Hello world"
        parsed.has_attachment = False
        parsed.label_ids = ["INBOX"]
        parsed.received_at = None
        parsed.body_text = body_text
        parsed.body_html = body_html
        return parsed

    def _make_user(self):
        user = MagicMock()
        user.id = TEST_USER_ID
        return user

    def _make_oauth_token(self):
        token = MagicMock()
        token.encrypted_access_token = b"fake-access"
        token.encrypted_refresh_token = b"fake-refresh"
        return token

    def _make_session(self, inserted=True):
        session = MagicMock()
        result = MagicMock()
        if inserted:
            result.fetchone.return_value = (uuid.uuid4(),)
        else:
            result.fetchone.return_value = None
        session.execute.return_value = result
        return session

    @patch("app.tasks.gmail_tasks.parse_gmail_message")
    @patch("app.tasks.gmail_tasks.get_crypto_service")
    def test_stores_encrypted_content_when_opted_in(
        self, mock_get_crypto, mock_parse,
    ):
        parsed = self._make_parsed()
        mock_parse.return_value = parsed

        mock_crypto = MagicMock()
        mock_crypto.encrypt.side_effect = lambda text: f"enc:{text}".encode()
        mock_get_crypto.return_value = mock_crypto

        user_pref = MagicMock()
        user_pref.store_email_content = True
        user_pref.auto_categorize_enabled = False
        user_pref.auto_label_enabled = False

        session = self._make_session(inserted=True)
        gmail = MagicMock()
        loop_mock = MagicMock()
        loop_mock.run_until_complete.return_value = {"id": "msg_test_001"}

        with patch("asyncio.new_event_loop", return_value=loop_mock):
            _process_single_message(
                session=session,
                user=self._make_user(),
                gmail=gmail,
                oauth_token=self._make_oauth_token(),
                message_id="msg_test_001",
                rule_dicts=[],
                settings=MagicMock(),
                user_pref=user_pref,
            )

        # Check that pg_insert was called with encrypted content
        insert_call = session.execute.call_args_list[0]
        stmt = insert_call[0][0]
        # The statement should have been built with encrypted values
        # Verify crypto.encrypt was called for body_text and body_html
        assert mock_crypto.encrypt.call_count == 2
        mock_crypto.encrypt.assert_any_call("Hello world")
        mock_crypto.encrypt.assert_any_call("<p>Hello</p>")

    @patch("app.tasks.gmail_tasks.parse_gmail_message")
    def test_no_encrypted_content_when_opted_out(self, mock_parse):
        parsed = self._make_parsed()
        mock_parse.return_value = parsed

        user_pref = MagicMock()
        user_pref.store_email_content = False
        user_pref.auto_categorize_enabled = False
        user_pref.auto_label_enabled = False

        session = self._make_session(inserted=True)
        gmail = MagicMock()
        loop_mock = MagicMock()
        loop_mock.run_until_complete.return_value = {"id": "msg_test_001"}

        with patch("asyncio.new_event_loop", return_value=loop_mock), \
             patch("app.tasks.gmail_tasks.get_crypto_service") as mock_get_crypto:
            _process_single_message(
                session=session,
                user=self._make_user(),
                gmail=gmail,
                oauth_token=self._make_oauth_token(),
                message_id="msg_test_001",
                rule_dicts=[],
                settings=MagicMock(),
                user_pref=user_pref,
            )

            # crypto.encrypt should NOT have been called
            mock_get_crypto.return_value.encrypt.assert_not_called()

    @patch("app.tasks.gmail_tasks.parse_gmail_message")
    def test_no_encrypted_content_when_no_preference(self, mock_parse):
        parsed = self._make_parsed()
        mock_parse.return_value = parsed

        session = self._make_session(inserted=True)
        gmail = MagicMock()
        loop_mock = MagicMock()
        loop_mock.run_until_complete.return_value = {"id": "msg_test_001"}

        with patch("asyncio.new_event_loop", return_value=loop_mock), \
             patch("app.tasks.gmail_tasks.get_crypto_service") as mock_get_crypto:
            _process_single_message(
                session=session,
                user=self._make_user(),
                gmail=gmail,
                oauth_token=self._make_oauth_token(),
                message_id="msg_test_001",
                rule_dicts=[],
                settings=MagicMock(),
                user_pref=None,  # No preference set
            )

            # crypto.encrypt should NOT have been called
            mock_get_crypto.return_value.encrypt.assert_not_called()

    @patch("app.tasks.gmail_tasks.parse_gmail_message")
    @patch("app.tasks.gmail_tasks.get_crypto_service")
    def test_handles_none_body_text_gracefully(self, mock_get_crypto, mock_parse):
        """If body_text is None, encryption is skipped for that field."""
        parsed = self._make_parsed(body_text=None, body_html="<p>Hi</p>")
        mock_parse.return_value = parsed

        mock_crypto = MagicMock()
        mock_crypto.encrypt.side_effect = lambda text: f"enc:{text}".encode()
        mock_get_crypto.return_value = mock_crypto

        user_pref = MagicMock()
        user_pref.store_email_content = True
        user_pref.auto_categorize_enabled = False
        user_pref.auto_label_enabled = False

        session = self._make_session(inserted=True)
        gmail = MagicMock()
        loop_mock = MagicMock()
        loop_mock.run_until_complete.return_value = {"id": "msg_test_001"}

        with patch("asyncio.new_event_loop", return_value=loop_mock):
            _process_single_message(
                session=session,
                user=self._make_user(),
                gmail=gmail,
                oauth_token=self._make_oauth_token(),
                message_id="msg_test_001",
                rule_dicts=[],
                settings=MagicMock(),
                user_pref=user_pref,
            )

        # Only body_html should have been encrypted (body_text is None)
        assert mock_crypto.encrypt.call_count == 1
        mock_crypto.encrypt.assert_called_once_with("<p>Hi</p>")


# ---------------------------------------------------------------------------
# Export decryption tests
# ---------------------------------------------------------------------------


class TestExportDecryptsEmailContent:

    def test_serialize_row_decrypts_email_content(self):
        from app.routers.admin import _serialize_row

        obj = MagicMock()
        obj.message_id = "msg_001"
        obj.subject = "Test"
        obj.encrypted_body_text = b"ciphertext-body"
        obj.encrypted_body_html = b"ciphertext-html"

        cols = []
        for key in ("message_id", "subject", "encrypted_body_text", "encrypted_body_html"):
            col = MagicMock()
            col.key = key
            cols.append(col)
        type(obj).__mapper__ = MagicMock()
        type(obj).__mapper__.columns = cols

        def mock_decrypt(ciphertext: bytes) -> str:
            return f"plain:{ciphertext.decode()}"

        result = _serialize_row(obj, decrypt_fn=mock_decrypt)
        assert result["body_text"] == "plain:ciphertext-body"
        assert result["body_html"] == "plain:ciphertext-html"
        assert result["message_id"] == "msg_001"
        assert result["subject"] == "Test"
