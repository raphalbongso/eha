"""Unit tests for the follow-up reminder feature.

Covers:
- FollowUpReminder model and ReminderStatus enum validation
- FollowUpReminderCreate / FollowUpReminderResponse Pydantic schemas
- check_follow_up_reminders periodic task logic (with full mocking)
- Auto-dismissal when thread replies exist
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.models.follow_up_reminder import FollowUpReminder, ReminderStatus
from app.schemas.automation import FollowUpReminderCreate, FollowUpReminderResponse
from app.tasks.automation_tasks import check_follow_up_reminders


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reminder(
    *,
    user_id=None,
    message_id="msg_001",
    thread_id="thread_001",
    remind_after_hours=72,
    status=ReminderStatus.PENDING,
    triggered_at=None,
    created_at=None,
    reminder_id=None,
):
    """Build a mock FollowUpReminder with sensible defaults."""
    r = MagicMock(spec=FollowUpReminder)
    r.id = reminder_id or uuid.uuid4()
    r.user_id = user_id or uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    r.message_id = message_id
    r.thread_id = thread_id
    r.remind_after_hours = remind_after_hours
    r.status = status
    r.triggered_at = triggered_at
    r.created_at = created_at or (datetime.now(timezone.utc) - timedelta(hours=100))
    return r


def _make_oauth_token(user_id):
    token = MagicMock()
    token.user_id = user_id
    token.encrypted_access_token = "enc-access-tok"
    token.encrypted_refresh_token = "enc-refresh-tok"
    return token


def _make_processed_message(user_id, message_id, subject="Re: Project Update"):
    pm = MagicMock()
    pm.user_id = user_id
    pm.message_id = message_id
    pm.subject = subject
    return pm


def _make_device_token(user_id, platform="ios", token="device-tok-abc"):
    dt = MagicMock()
    dt.user_id = user_id
    dt.platform = platform
    dt.token = token
    return dt


# ---------------------------------------------------------------------------
# ReminderStatus enum
# ---------------------------------------------------------------------------

class TestReminderStatus:
    def test_values(self):
        assert ReminderStatus.PENDING == "pending"
        assert ReminderStatus.TRIGGERED == "triggered"
        assert ReminderStatus.DISMISSED == "dismissed"

    def test_is_string_subclass(self):
        assert isinstance(ReminderStatus.PENDING, str)

    def test_all_members(self):
        members = list(ReminderStatus)
        assert len(members) == 3
        assert set(m.value for m in members) == {"pending", "triggered", "dismissed"}


# ---------------------------------------------------------------------------
# FollowUpReminder model (structural / repr)
# ---------------------------------------------------------------------------

class TestFollowUpReminderModel:
    def test_repr(self):
        r = FollowUpReminder()
        r.id = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        r.status = ReminderStatus.PENDING
        assert "12345678-1234-1234-1234-123456789abc" in repr(r)
        assert "pending" in repr(r)

    def test_default_status_is_pending(self):
        """The model column default should be PENDING."""
        col = FollowUpReminder.__table__.c["status"]
        assert col.default.arg == ReminderStatus.PENDING

    def test_default_remind_after_hours_is_72(self):
        col = FollowUpReminder.__table__.c["remind_after_hours"]
        assert col.default.arg == 72

    def test_triggered_at_nullable(self):
        col = FollowUpReminder.__table__.c["triggered_at"]
        assert col.nullable is True

    def test_tablename(self):
        assert FollowUpReminder.__tablename__ == "follow_up_reminders"

    def test_status_transition_pending_to_triggered(self):
        """Status can be set from PENDING to TRIGGERED."""
        r = _make_reminder(status=ReminderStatus.PENDING)
        r.status = ReminderStatus.TRIGGERED
        assert r.status == ReminderStatus.TRIGGERED

    def test_status_transition_pending_to_dismissed(self):
        """Status can be set from PENDING to DISMISSED."""
        r = _make_reminder(status=ReminderStatus.PENDING)
        r.status = ReminderStatus.DISMISSED
        assert r.status == ReminderStatus.DISMISSED


# ---------------------------------------------------------------------------
# FollowUpReminderCreate schema
# ---------------------------------------------------------------------------

class TestFollowUpReminderCreateSchema:
    def test_valid_minimal(self):
        schema = FollowUpReminderCreate(message_id="msg_001", thread_id="thread_001")
        assert schema.message_id == "msg_001"
        assert schema.thread_id == "thread_001"
        assert schema.remind_after_hours == 72  # default

    def test_valid_custom_hours(self):
        schema = FollowUpReminderCreate(
            message_id="msg_002", thread_id="thread_002", remind_after_hours=24
        )
        assert schema.remind_after_hours == 24

    def test_hours_minimum_boundary(self):
        schema = FollowUpReminderCreate(
            message_id="m", thread_id="t", remind_after_hours=1
        )
        assert schema.remind_after_hours == 1

    def test_hours_maximum_boundary(self):
        schema = FollowUpReminderCreate(
            message_id="m", thread_id="t", remind_after_hours=720
        )
        assert schema.remind_after_hours == 720

    def test_hours_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            FollowUpReminderCreate(
                message_id="m", thread_id="t", remind_after_hours=0
            )

    def test_hours_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            FollowUpReminderCreate(
                message_id="m", thread_id="t", remind_after_hours=721
            )

    def test_missing_message_id_rejected(self):
        with pytest.raises(ValidationError):
            FollowUpReminderCreate(thread_id="t")

    def test_missing_thread_id_rejected(self):
        with pytest.raises(ValidationError):
            FollowUpReminderCreate(message_id="m")


# ---------------------------------------------------------------------------
# FollowUpReminderResponse schema
# ---------------------------------------------------------------------------

class TestFollowUpReminderResponseSchema:
    def test_from_attributes(self):
        """Schema should work with from_attributes=True (ORM mode)."""
        now = datetime.now(timezone.utc)
        rid = uuid.uuid4()
        uid = uuid.uuid4()

        obj = MagicMock()
        obj.id = rid
        obj.user_id = uid
        obj.message_id = "msg_001"
        obj.thread_id = "thread_001"
        obj.remind_after_hours = 48
        obj.status = "pending"
        obj.triggered_at = None
        obj.created_at = now

        schema = FollowUpReminderResponse.model_validate(obj, from_attributes=True)
        assert schema.id == rid
        assert schema.user_id == uid
        assert schema.message_id == "msg_001"
        assert schema.thread_id == "thread_001"
        assert schema.remind_after_hours == 48
        assert schema.status == "pending"
        assert schema.triggered_at is None
        assert schema.created_at == now

    def test_triggered_at_populated(self):
        now = datetime.now(timezone.utc)
        obj = MagicMock()
        obj.id = uuid.uuid4()
        obj.user_id = uuid.uuid4()
        obj.message_id = "m"
        obj.thread_id = "t"
        obj.remind_after_hours = 72
        obj.status = "triggered"
        obj.triggered_at = now
        obj.created_at = now - timedelta(days=4)

        schema = FollowUpReminderResponse.model_validate(obj, from_attributes=True)
        assert schema.triggered_at == now
        assert schema.status == "triggered"

    def test_from_dict(self):
        now = datetime.now(timezone.utc)
        data = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "message_id": "msg_xyz",
            "thread_id": "thread_xyz",
            "remind_after_hours": 24,
            "status": "dismissed",
            "triggered_at": None,
            "created_at": now,
        }
        schema = FollowUpReminderResponse(**data)
        assert schema.status == "dismissed"


# ---------------------------------------------------------------------------
# check_follow_up_reminders task — helpers
# ---------------------------------------------------------------------------

def _build_db_for_check(
    reminders,
    oauth_token=None,
    thread_response=None,
    processed_message=None,
    devices=None,
):
    """Create a mock async DB session for check_follow_up_reminders.

    The task issues multiple execute() calls in sequence:
      1. SELECT reminders (pending)
      Then per-reminder:
        2. SELECT OAuthToken (for Gmail access)
        3. SELECT ProcessedMessage (for subject)
        4. SELECT DeviceToken (for push)
    """
    db = AsyncMock()

    # Build side-effect list for db.execute()
    call_results = []

    # 1st call: pending reminders
    reminders_result = MagicMock()
    reminders_result.scalars.return_value.all.return_value = reminders
    call_results.append(reminders_result)

    # Per-reminder calls
    for _ in reminders:
        # OAuth token lookup
        oauth_result = MagicMock()
        oauth_result.scalar_one_or_none.return_value = oauth_token
        call_results.append(oauth_result)

        # ProcessedMessage lookup (only reached if no reply => triggered path)
        if processed_message is not None:
            pm_result = MagicMock()
            pm_result.scalar_one_or_none.return_value = processed_message
            call_results.append(pm_result)

        # Device tokens lookup
        if devices is not None:
            dev_result = MagicMock()
            dev_result.scalars.return_value.all.return_value = devices
            call_results.append(dev_result)

    db.execute = AsyncMock(side_effect=call_results)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def _run_check(
    reminders,
    oauth_token=None,
    thread_response=None,
    processed_message=None,
    devices=None,
    gmail_get_thread_side_effect=None,
):
    """Run check_follow_up_reminders synchronously with full mocking."""
    db = _build_db_for_check(
        reminders=reminders,
        oauth_token=oauth_token,
        thread_response=thread_response,
        processed_message=processed_message,
        devices=devices,
    )

    session_factory = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=db),
        __aexit__=AsyncMock(return_value=False),
    ))

    mock_gmail_instance = AsyncMock()
    if gmail_get_thread_side_effect is not None:
        mock_gmail_instance.get_thread.side_effect = gmail_get_thread_side_effect
    elif thread_response is not None:
        mock_gmail_instance.get_thread.return_value = thread_response
    else:
        mock_gmail_instance.get_thread.return_value = {"messages": []}

    mock_push = AsyncMock()

    with patch("app.tasks.automation_tasks._get_async_session", return_value=session_factory), \
         patch("app.tasks.automation_tasks.get_settings") as mock_settings, \
         patch("app.services.crypto_service.get_crypto_service") as mock_crypto, \
         patch("app.services.gmail_service.GmailService", return_value=mock_gmail_instance), \
         patch("app.tasks.automation_tasks.get_push_service", return_value=mock_push):
        mock_settings.return_value = MagicMock()
        mock_crypto.return_value = MagicMock()

        check_follow_up_reminders.__wrapped__()

    return db, mock_gmail_instance, mock_push


# ---------------------------------------------------------------------------
# check_follow_up_reminders — tests
# ---------------------------------------------------------------------------

class TestCheckFollowUpReminders:
    """Tests for the periodic check_follow_up_reminders task."""

    def test_no_pending_reminders(self):
        """Task exits cleanly when there are no pending reminders."""
        db, gmail, push = _run_check(reminders=[])
        gmail.get_thread.assert_not_called()
        push.send.assert_not_called()

    def test_skips_reminder_before_deadline(self):
        """Reminders whose deadline has not yet passed should be skipped."""
        reminder = _make_reminder(
            remind_after_hours=72,
            created_at=datetime.now(timezone.utc) - timedelta(hours=10),  # 62 hours early
        )
        db, gmail, push = _run_check(reminders=[reminder])

        # Should not check Gmail since deadline is not reached
        gmail.get_thread.assert_not_called()
        push.send.assert_not_called()
        # Status should remain pending (unchanged)
        assert reminder.status == ReminderStatus.PENDING

    def test_skips_when_no_oauth_token(self):
        """Reminder past deadline but user has no OAuth token should be skipped."""
        reminder = _make_reminder(
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=None,
        )
        gmail.get_thread.assert_not_called()
        assert reminder.status == ReminderStatus.PENDING

    def test_dismisses_when_reply_exists(self):
        """When a reply exists after the original message, the reminder should be dismissed."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            thread_id="thread_abc",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)
        thread_response = {
            "messages": [
                {"id": "msg_original"},
                {"id": "msg_reply_1"},  # Reply after original
            ]
        }

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            thread_response=thread_response,
        )

        assert reminder.status == ReminderStatus.DISMISSED
        push.send.assert_not_called()

    def test_triggers_when_no_reply(self):
        """When no reply exists, the reminder should be triggered with a push notification."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            thread_id="thread_abc",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)
        pm = _make_processed_message(user_id, "msg_original", subject="Project Update")
        device = _make_device_token(user_id, platform="ios", token="tok-1")

        thread_response = {
            "messages": [
                {"id": "msg_original"},
                # No subsequent messages
            ]
        }

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            thread_response=thread_response,
            processed_message=pm,
            devices=[device],
        )

        assert reminder.status == ReminderStatus.TRIGGERED
        assert reminder.triggered_at is not None
        push.send.assert_called_once()
        call_kwargs = push.send.call_args.kwargs
        assert call_kwargs["platform"] == "ios"
        assert call_kwargs["token"] == "tok-1"
        assert call_kwargs["title"] == "EHA: No reply received"
        assert "Project Update" in call_kwargs["body"]
        assert call_kwargs["extra_data"]["thread_id"] == "thread_abc"
        assert call_kwargs["extra_data"]["reminder_id"] == str(reminder.id)

    def test_triggers_with_unknown_subject_when_no_processed_message(self):
        """When ProcessedMessage is missing, subject should fall back to '(unknown subject)'."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)
        device = _make_device_token(user_id)

        thread_response = {"messages": [{"id": "msg_original"}]}

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            thread_response=thread_response,
            processed_message=None,
            devices=[device],
        )

        assert reminder.status == ReminderStatus.TRIGGERED
        call_kwargs = push.send.call_args.kwargs
        assert "(unknown subject)" in call_kwargs["body"]

    def test_sends_to_multiple_devices(self):
        """Push notifications should be sent to every registered device."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)
        pm = _make_processed_message(user_id, "msg_original")
        devices = [
            _make_device_token(user_id, platform="ios", token="tok-ios"),
            _make_device_token(user_id, platform="android", token="tok-android"),
        ]

        thread_response = {"messages": [{"id": "msg_original"}]}

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            thread_response=thread_response,
            processed_message=pm,
            devices=devices,
        )

        assert push.send.call_count == 2
        platforms_notified = {c.kwargs["platform"] for c in push.send.call_args_list}
        assert platforms_notified == {"ios", "android"}

    def test_continues_on_gmail_api_error(self):
        """If Gmail API call fails, the reminder is skipped (not crashed)."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            gmail_get_thread_side_effect=Exception("Gmail API unavailable"),
        )

        # Status should remain unchanged (skipped)
        assert reminder.status == ReminderStatus.PENDING
        push.send.assert_not_called()

    def test_thread_with_only_prior_messages_does_not_dismiss(self):
        """Messages before the original do NOT count as replies."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)
        pm = _make_processed_message(user_id, "msg_original")
        device = _make_device_token(user_id)

        # msg_prior comes before msg_original in the thread
        thread_response = {
            "messages": [
                {"id": "msg_prior"},
                {"id": "msg_original"},
            ]
        }

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            thread_response=thread_response,
            processed_message=pm,
            devices=[device],
        )

        # No reply after original, so it should be triggered, not dismissed
        assert reminder.status == ReminderStatus.TRIGGERED
        push.send.assert_called_once()

    def test_empty_thread_triggers_notification(self):
        """If thread is empty (no messages at all), treat as no reply."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)
        pm = _make_processed_message(user_id, "msg_original")
        device = _make_device_token(user_id)

        thread_response = {"messages": []}

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            thread_response=thread_response,
            processed_message=pm,
            devices=[device],
        )

        assert reminder.status == ReminderStatus.TRIGGERED
        push.send.assert_called_once()


# ---------------------------------------------------------------------------
# Auto-dismiss integration scenarios
# ---------------------------------------------------------------------------

class TestAutoDismissOnReply:
    """Verify auto-dismiss logic when replies exist in thread."""

    def test_dismiss_with_multiple_replies(self):
        """Multiple replies after original should still dismiss."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)

        thread_response = {
            "messages": [
                {"id": "msg_original"},
                {"id": "msg_reply_1"},
                {"id": "msg_reply_2"},
                {"id": "msg_reply_3"},
            ]
        }

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            thread_response=thread_response,
        )

        assert reminder.status == ReminderStatus.DISMISSED
        push.send.assert_not_called()

    def test_dismiss_only_checks_messages_after_original(self):
        """Prior messages should be ignored; only messages after original matter."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)
        pm = _make_processed_message(user_id, "msg_original")
        device = _make_device_token(user_id)

        # Three messages before original, none after
        thread_response = {
            "messages": [
                {"id": "msg_earlier_1"},
                {"id": "msg_earlier_2"},
                {"id": "msg_earlier_3"},
                {"id": "msg_original"},
            ]
        }

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            thread_response=thread_response,
            processed_message=pm,
            devices=[device],
        )

        # No reply after original => trigger, not dismiss
        assert reminder.status == ReminderStatus.TRIGGERED
        push.send.assert_called_once()

    def test_original_not_in_thread_triggers(self):
        """If the original message_id is absent from the thread, treat as no reply."""
        user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        reminder = _make_reminder(
            user_id=user_id,
            message_id="msg_original",
            remind_after_hours=24,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        oauth = _make_oauth_token(user_id)
        pm = _make_processed_message(user_id, "msg_original")
        device = _make_device_token(user_id)

        thread_response = {
            "messages": [
                {"id": "msg_unrelated_1"},
                {"id": "msg_unrelated_2"},
            ]
        }

        db, gmail, push = _run_check(
            reminders=[reminder],
            oauth_token=oauth,
            thread_response=thread_response,
            processed_message=pm,
            devices=[device],
        )

        # Original not found, found_original stays False, so has_reply stays False
        assert reminder.status == ReminderStatus.TRIGGERED
        push.send.assert_called_once()
