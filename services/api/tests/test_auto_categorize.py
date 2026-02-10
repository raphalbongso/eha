"""Tests for auto-categorize and auto-label flow."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_service import Summary
from app.services.gmail_service import GmailService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_gmail_service():
    """Create a GmailService with mocked settings and crypto."""
    settings = MagicMock()
    settings.google_client_id = "fake-client-id"
    settings.google_client_secret = MagicMock()
    settings.google_client_secret.get_secret_value.return_value = "fake-secret"
    crypto = MagicMock()
    crypto.decrypt.return_value = "decrypted-token"
    return GmailService(settings, crypto)


def _make_user(user_id: uuid.UUID | None = None):
    user = MagicMock()
    user.id = user_id or uuid.UUID("12345678-1234-1234-1234-123456789abc")
    user.email = "test@example.com"
    return user


def _make_oauth_token():
    token = MagicMock()
    token.encrypted_access_token = b"enc-access"
    token.encrypted_refresh_token = b"enc-refresh"
    token.last_history_id = "9999"
    return token


def _make_user_pref(auto_categorize: bool = True, auto_label: bool = True):
    pref = MagicMock()
    pref.auto_categorize_enabled = auto_categorize
    pref.auto_label_enabled = auto_label
    return pref


def _make_raw_gmail_message(msg_id: str = "msg_100"):
    """Minimal raw Gmail API message dict for parsing."""
    return {
        "id": msg_id,
        "threadId": "thread_100",
        "labelIds": ["INBOX"],
        "snippet": "Please review the attached invoice.",
        "internalDate": "1706745600000",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "vendor@example.com"},
                {"name": "To", "value": "test@example.com"},
                {"name": "Subject", "value": "Invoice #1234"},
            ],
            "body": {
                "data": "UGxlYXNlIHJldmlldyB0aGUgYXR0YWNoZWQgaW52b2ljZS4=",
            },
        },
    }


# ---------------------------------------------------------------------------
# GmailService.get_or_create_label
# ---------------------------------------------------------------------------

class TestGetOrCreateLabel:
    """Test GmailService.get_or_create_label with mocked Gmail API."""

    def test_returns_existing_label_id(self):
        """When a label already exists, return its ID without creating."""
        gmail = _make_mock_gmail_service()

        mock_service = MagicMock()
        labels_response = {
            "labels": [
                {"id": "Label_1", "name": "INBOX"},
                {"id": "Label_42", "name": "EHA/invoice"},
            ]
        }
        mock_service.users().labels().list(userId="me").execute.return_value = labels_response

        with patch.object(gmail, "_get_credentials", return_value=MagicMock()):
            with patch.object(gmail, "_build_service", return_value=mock_service):
                result = asyncio.get_event_loop().run_until_complete(
                    gmail.get_or_create_label(
                        encrypted_access_token=b"enc",
                        encrypted_refresh_token=b"enc",
                        label_name="EHA/invoice",
                    )
                )

        assert result == "Label_42"
        # Should NOT call create when label exists
        mock_service.users().labels().create.assert_not_called()

    def test_creates_label_when_not_found(self):
        """When the label does not exist, create it and return the new ID."""
        gmail = _make_mock_gmail_service()

        mock_service = MagicMock()
        labels_response = {"labels": [{"id": "Label_1", "name": "INBOX"}]}
        mock_service.users().labels().list(userId="me").execute.return_value = labels_response

        created_response = {"id": "Label_99", "name": "EHA/meeting"}
        mock_service.users().labels().create(userId="me", body={
            "name": "EHA/meeting",
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }).execute.return_value = created_response

        with patch.object(gmail, "_get_credentials", return_value=MagicMock()):
            with patch.object(gmail, "_build_service", return_value=mock_service):
                result = asyncio.get_event_loop().run_until_complete(
                    gmail.get_or_create_label(
                        encrypted_access_token=b"enc",
                        encrypted_refresh_token=b"enc",
                        label_name="EHA/meeting",
                    )
                )

        assert result == "Label_99"

    def test_returns_label_with_empty_label_list(self):
        """When the API returns no labels at all, create the requested label."""
        gmail = _make_mock_gmail_service()

        mock_service = MagicMock()
        mock_service.users().labels().list(userId="me").execute.return_value = {"labels": []}

        created_response = {"id": "Label_new", "name": "EHA/security"}
        mock_service.users().labels().create(userId="me", body={
            "name": "EHA/security",
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }).execute.return_value = created_response

        with patch.object(gmail, "_get_credentials", return_value=MagicMock()):
            with patch.object(gmail, "_build_service", return_value=mock_service):
                result = asyncio.get_event_loop().run_until_complete(
                    gmail.get_or_create_label(
                        encrypted_access_token=b"enc",
                        encrypted_refresh_token=b"enc",
                        label_name="EHA/security",
                    )
                )

        assert result == "Label_new"


# ---------------------------------------------------------------------------
# GmailService.modify_message_labels
# ---------------------------------------------------------------------------

class TestModifyMessageLabels:
    """Test GmailService.modify_message_labels with mocked Gmail API."""

    def test_add_labels(self):
        """Adding label IDs sends correct body to Gmail API."""
        gmail = _make_mock_gmail_service()

        mock_service = MagicMock()
        modify_response = {"id": "msg_100", "labelIds": ["INBOX", "Label_42"]}
        mock_service.users().messages().modify(
            userId="me", id="msg_100", body={"addLabelIds": ["Label_42"]}
        ).execute.return_value = modify_response

        with patch.object(gmail, "_get_credentials", return_value=MagicMock()):
            with patch.object(gmail, "_build_service", return_value=mock_service):
                result = asyncio.get_event_loop().run_until_complete(
                    gmail.modify_message_labels(
                        encrypted_access_token=b"enc",
                        encrypted_refresh_token=b"enc",
                        message_id="msg_100",
                        add_label_ids=["Label_42"],
                    )
                )

        assert result["id"] == "msg_100"
        assert "Label_42" in result["labelIds"]

    def test_remove_labels(self):
        """Removing label IDs sends correct body to Gmail API."""
        gmail = _make_mock_gmail_service()

        mock_service = MagicMock()
        modify_response = {"id": "msg_200", "labelIds": ["INBOX"]}
        mock_service.users().messages().modify(
            userId="me", id="msg_200", body={"removeLabelIds": ["SPAM"]}
        ).execute.return_value = modify_response

        with patch.object(gmail, "_get_credentials", return_value=MagicMock()):
            with patch.object(gmail, "_build_service", return_value=mock_service):
                result = asyncio.get_event_loop().run_until_complete(
                    gmail.modify_message_labels(
                        encrypted_access_token=b"enc",
                        encrypted_refresh_token=b"enc",
                        message_id="msg_200",
                        remove_label_ids=["SPAM"],
                    )
                )

        assert result["id"] == "msg_200"

    def test_add_and_remove_labels(self):
        """Both add and remove in a single call."""
        gmail = _make_mock_gmail_service()

        mock_service = MagicMock()
        modify_response = {"id": "msg_300", "labelIds": ["Label_new"]}
        mock_service.users().messages().modify(
            userId="me",
            id="msg_300",
            body={"addLabelIds": ["Label_new"], "removeLabelIds": ["Label_old"]},
        ).execute.return_value = modify_response

        with patch.object(gmail, "_get_credentials", return_value=MagicMock()):
            with patch.object(gmail, "_build_service", return_value=mock_service):
                result = asyncio.get_event_loop().run_until_complete(
                    gmail.modify_message_labels(
                        encrypted_access_token=b"enc",
                        encrypted_refresh_token=b"enc",
                        message_id="msg_300",
                        add_label_ids=["Label_new"],
                        remove_label_ids=["Label_old"],
                    )
                )

        assert result["id"] == "msg_300"


# ---------------------------------------------------------------------------
# _process_single_message: auto-categorize + auto-label
# ---------------------------------------------------------------------------

class TestProcessSingleMessageAutoCategorize:
    """Test that _process_single_message calls AI categorize and label APIs."""

    @patch("app.tasks.gmail_tasks.evaluate_rule", return_value=False)
    @patch("app.services.ai_service.get_ai_service")
    def test_auto_categorize_and_label_when_enabled(self, mock_get_ai, mock_eval_rule):
        """When both auto_categorize and auto_label are enabled, AI is called
        and the resulting category label is applied in Gmail."""
        from app.tasks.gmail_tasks import _process_single_message

        # AI service returns a summary with category
        mock_ai = MagicMock()
        mock_ai.summarize = AsyncMock(
            return_value=Summary(
                summary="Invoice from vendor.",
                action_items=["Pay invoice"],
                urgency="medium",
                category="invoice",
                priority_score=70,
                priority_signals=["contains deadline"],
            )
        )
        mock_get_ai.return_value = mock_ai

        # GmailService mocks
        gmail = MagicMock(spec=GmailService)
        gmail.get_message = AsyncMock(return_value=_make_raw_gmail_message("msg_100"))
        gmail.get_or_create_label = AsyncMock(return_value="Label_42")
        gmail.modify_message_labels = AsyncMock(
            return_value={"id": "msg_100", "labelIds": ["INBOX", "Label_42"]}
        )

        # Session mock: simulate successful insert (not a duplicate)
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (uuid.uuid4(),)
        session.execute.return_value = mock_result

        user = _make_user()
        oauth_token = _make_oauth_token()
        user_pref = _make_user_pref(auto_categorize=True, auto_label=True)

        _process_single_message(
            session=session,
            user=user,
            gmail=gmail,
            oauth_token=oauth_token,
            message_id="msg_100",
            rule_dicts=[],
            settings=MagicMock(),
            user_pref=user_pref,
        )

        # AI summarize was called
        mock_ai.summarize.assert_called_once()

        # Label was created/fetched and applied
        gmail.get_or_create_label.assert_called_once()
        call_kwargs = gmail.get_or_create_label.call_args
        assert call_kwargs[1]["label_name"] == "EHA/invoice" or call_kwargs[0][-1] == "EHA/invoice"

        gmail.modify_message_labels.assert_called_once()

    @patch("app.tasks.gmail_tasks.evaluate_rule", return_value=False)
    @patch("app.services.ai_service.get_ai_service")
    def test_categorize_only_no_label(self, mock_get_ai, mock_eval_rule):
        """When auto_categorize is enabled but auto_label is disabled,
        AI is called for categorization but no Gmail label is applied."""
        from app.tasks.gmail_tasks import _process_single_message

        mock_ai = MagicMock()
        mock_ai.summarize = AsyncMock(
            return_value=Summary(
                summary="Newsletter update.",
                action_items=[],
                urgency="low",
                category="newsletter",
                priority_score=20,
                priority_signals=[],
            )
        )
        mock_get_ai.return_value = mock_ai

        gmail = MagicMock(spec=GmailService)
        gmail.get_message = AsyncMock(return_value=_make_raw_gmail_message())
        gmail.get_or_create_label = AsyncMock()
        gmail.modify_message_labels = AsyncMock()

        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (uuid.uuid4(),)
        session.execute.return_value = mock_result

        user_pref = _make_user_pref(auto_categorize=True, auto_label=False)

        _process_single_message(
            session=session,
            user=_make_user(),
            gmail=gmail,
            oauth_token=_make_oauth_token(),
            message_id="msg_200",
            rule_dicts=[],
            settings=MagicMock(),
            user_pref=user_pref,
        )

        # AI was still called
        mock_ai.summarize.assert_called_once()

        # No label operations
        gmail.get_or_create_label.assert_not_called()
        gmail.modify_message_labels.assert_not_called()


class TestProcessSingleMessageSkipsAutoCategorize:
    """Test that _process_single_message skips auto-categorize when disabled."""

    @patch("app.tasks.gmail_tasks.evaluate_rule", return_value=False)
    def test_skips_when_user_pref_is_none(self, mock_eval_rule):
        """When user_pref is None, no AI categorization or labeling occurs."""
        from app.tasks.gmail_tasks import _process_single_message

        gmail = MagicMock(spec=GmailService)
        gmail.get_message = AsyncMock(return_value=_make_raw_gmail_message())
        gmail.get_or_create_label = AsyncMock()
        gmail.modify_message_labels = AsyncMock()

        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (uuid.uuid4(),)
        session.execute.return_value = mock_result

        with patch("app.services.ai_service.get_ai_service") as mock_get_ai:
            _process_single_message(
                session=session,
                user=_make_user(),
                gmail=gmail,
                oauth_token=_make_oauth_token(),
                message_id="msg_300",
                rule_dicts=[],
                settings=MagicMock(),
                user_pref=None,
            )

            mock_get_ai.assert_not_called()

        gmail.get_or_create_label.assert_not_called()
        gmail.modify_message_labels.assert_not_called()

    @patch("app.tasks.gmail_tasks.evaluate_rule", return_value=False)
    def test_skips_when_both_disabled(self, mock_eval_rule):
        """When both auto_categorize and auto_label are False, AI is not called."""
        from app.tasks.gmail_tasks import _process_single_message

        gmail = MagicMock(spec=GmailService)
        gmail.get_message = AsyncMock(return_value=_make_raw_gmail_message())
        gmail.get_or_create_label = AsyncMock()
        gmail.modify_message_labels = AsyncMock()

        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (uuid.uuid4(),)
        session.execute.return_value = mock_result

        user_pref = _make_user_pref(auto_categorize=False, auto_label=False)

        with patch("app.services.ai_service.get_ai_service") as mock_get_ai:
            _process_single_message(
                session=session,
                user=_make_user(),
                gmail=gmail,
                oauth_token=_make_oauth_token(),
                message_id="msg_400",
                rule_dicts=[],
                settings=MagicMock(),
                user_pref=user_pref,
            )

            mock_get_ai.assert_not_called()

        gmail.get_or_create_label.assert_not_called()
        gmail.modify_message_labels.assert_not_called()

    @patch("app.tasks.gmail_tasks.evaluate_rule", return_value=False)
    @patch("app.services.ai_service.get_ai_service")
    def test_skips_label_when_ai_returns_none(self, mock_get_ai, mock_eval_rule):
        """When AI summarize returns None, category stays None and no label is applied."""
        from app.tasks.gmail_tasks import _process_single_message

        mock_ai = MagicMock()
        mock_ai.summarize = AsyncMock(return_value=None)
        mock_get_ai.return_value = mock_ai

        gmail = MagicMock(spec=GmailService)
        gmail.get_message = AsyncMock(return_value=_make_raw_gmail_message())
        gmail.get_or_create_label = AsyncMock()
        gmail.modify_message_labels = AsyncMock()

        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (uuid.uuid4(),)
        session.execute.return_value = mock_result

        user_pref = _make_user_pref(auto_categorize=True, auto_label=True)

        _process_single_message(
            session=session,
            user=_make_user(),
            gmail=gmail,
            oauth_token=_make_oauth_token(),
            message_id="msg_500",
            rule_dicts=[],
            settings=MagicMock(),
            user_pref=user_pref,
        )

        # AI was called but returned None
        mock_ai.summarize.assert_called_once()

        # No label operations since category is None
        gmail.get_or_create_label.assert_not_called()
        gmail.modify_message_labels.assert_not_called()

    @patch("app.tasks.gmail_tasks.evaluate_rule", return_value=False)
    @patch("app.services.ai_service.get_ai_service")
    def test_label_failure_does_not_crash(self, mock_get_ai, mock_eval_rule):
        """When auto-label raises an exception, the message is still processed."""
        from app.tasks.gmail_tasks import _process_single_message

        mock_ai = MagicMock()
        mock_ai.summarize = AsyncMock(
            return_value=Summary(
                summary="Security alert.",
                action_items=["Check account"],
                urgency="high",
                category="security",
                priority_score=95,
                priority_signals=["security alert"],
            )
        )
        mock_get_ai.return_value = mock_ai

        gmail = MagicMock(spec=GmailService)
        gmail.get_message = AsyncMock(return_value=_make_raw_gmail_message())
        gmail.get_or_create_label = AsyncMock(side_effect=Exception("Gmail API error"))
        gmail.modify_message_labels = AsyncMock()

        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (uuid.uuid4(),)
        session.execute.return_value = mock_result

        user_pref = _make_user_pref(auto_categorize=True, auto_label=True)

        # Should not raise -- label failure is caught and logged
        _process_single_message(
            session=session,
            user=_make_user(),
            gmail=gmail,
            oauth_token=_make_oauth_token(),
            message_id="msg_600",
            rule_dicts=[],
            settings=MagicMock(),
            user_pref=user_pref,
        )

        # Categorization happened
        mock_ai.summarize.assert_called_once()

        # Label creation was attempted but failed; modify should not have been reached
        gmail.get_or_create_label.assert_called_once()
        gmail.modify_message_labels.assert_not_called()

        # Session was still committed (message was inserted)
        session.commit.assert_called_once()
