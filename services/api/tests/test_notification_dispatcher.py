"""Unit tests for NotificationDispatcher."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notification_dispatcher import NotificationDispatcher
from app.services.push_service import NotificationType


@pytest.fixture
def user_id():
    return uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def mock_push():
    push = AsyncMock()
    push.send.return_value = True
    return push


@pytest.fixture
def mock_slack():
    slack = AsyncMock()
    slack.send.return_value = True
    return slack


@pytest.fixture
def mock_crypto():
    crypto = MagicMock()
    crypto.decrypt.return_value = "https://hooks.slack.com/services/T00/B00/xxxx"
    return crypto


@pytest.fixture
def dispatcher(mock_push, mock_slack, mock_crypto):
    return NotificationDispatcher(
        push_service=mock_push,
        slack_service=mock_slack,
        crypto_service=mock_crypto,
    )


def _make_device(platform="ios", token="tok-123"):
    d = MagicMock()
    d.platform = platform
    d.token = token
    return d


def _make_slack_config(is_enabled=True, enabled_types=None, webhook_url=b"encrypted"):
    cfg = MagicMock()
    cfg.is_enabled = is_enabled
    cfg.enabled_notification_types = enabled_types or []
    cfg.webhook_url = webhook_url
    return cfg


def _mock_db(devices=None, slack_config=None):
    """Mock async DB that returns devices then slack_config on successive execute() calls."""
    device_result = MagicMock()
    device_result.scalars.return_value.all.return_value = devices or []

    slack_result = MagicMock()
    slack_result.scalar_one_or_none.return_value = slack_config

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[device_result, slack_result])
    return db


class TestNotificationDispatcher:
    """Tests for NotificationDispatcher.notify()."""

    @pytest.mark.asyncio
    async def test_push_only_no_slack(self, dispatcher, mock_push, mock_slack, user_id):
        """When no Slack config exists, only push is sent."""
        device = _make_device()
        db = _mock_db(devices=[device], slack_config=None)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.RULE_MATCH,
        )

        assert result["push_sent"] == 1
        assert result["push_failed"] == 0
        assert result["slack_sent"] is None
        mock_push.send.assert_called_once()
        mock_slack.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_slack_only_no_devices(self, dispatcher, mock_push, mock_slack, user_id):
        """When no devices exist but Slack is configured, only Slack is sent."""
        slack_cfg = _make_slack_config()
        db = _mock_db(devices=[], slack_config=slack_cfg)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.DIGEST,
        )

        assert result["push_sent"] == 0
        assert result["slack_sent"] is True
        mock_push.send.assert_not_called()
        mock_slack.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_push_and_slack(self, dispatcher, mock_push, mock_slack, user_id):
        """When both devices and Slack exist, both channels fire."""
        device = _make_device()
        slack_cfg = _make_slack_config()
        db = _mock_db(devices=[device], slack_config=slack_cfg)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.FOLLOW_UP,
        )

        assert result["push_sent"] == 1
        assert result["slack_sent"] is True
        mock_push.send.assert_called_once()
        mock_slack.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_devices(self, dispatcher, mock_push, user_id):
        devices = [_make_device("ios", "tok-1"), _make_device("android", "tok-2")]
        db = _mock_db(devices=devices, slack_config=None)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.SYSTEM,
        )

        assert result["push_sent"] == 2
        assert mock_push.send.call_count == 2

    @pytest.mark.asyncio
    async def test_push_failure_tracked(self, dispatcher, mock_push, user_id):
        mock_push.send.return_value = False
        device = _make_device()
        db = _mock_db(devices=[device], slack_config=None)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.SYSTEM,
        )

        assert result["push_sent"] == 0
        assert result["push_failed"] == 1

    @pytest.mark.asyncio
    async def test_slack_disabled(self, dispatcher, mock_slack, user_id):
        """Disabled Slack config should not trigger Slack send."""
        slack_cfg = _make_slack_config(is_enabled=False)
        db = _mock_db(devices=[], slack_config=slack_cfg)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.RULE_MATCH,
        )

        assert result["slack_sent"] is None
        mock_slack.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_slack_type_filtering_allowed(self, dispatcher, mock_slack, user_id):
        """Slack with type filter that includes the sent type."""
        slack_cfg = _make_slack_config(enabled_types=["RULE_MATCH", "DIGEST"])
        db = _mock_db(devices=[], slack_config=slack_cfg)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.RULE_MATCH,
        )

        assert result["slack_sent"] is True
        mock_slack.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_slack_type_filtering_blocked(self, dispatcher, mock_slack, user_id):
        """Slack with type filter that excludes the sent type."""
        slack_cfg = _make_slack_config(enabled_types=["DIGEST"])
        db = _mock_db(devices=[], slack_config=slack_cfg)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.RULE_MATCH,
        )

        assert result["slack_sent"] is None
        mock_slack.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_slack_empty_types_means_all_allowed(self, dispatcher, mock_slack, user_id):
        """Empty enabled_notification_types means all types are allowed."""
        slack_cfg = _make_slack_config(enabled_types=[])
        db = _mock_db(devices=[], slack_config=slack_cfg)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.MEETING_PREP,
        )

        assert result["slack_sent"] is True

    @pytest.mark.asyncio
    async def test_slack_decrypt_failure(self, dispatcher, mock_crypto, mock_slack, user_id):
        """If decryption fails, slack_sent should be False."""
        mock_crypto.decrypt.side_effect = Exception("decrypt error")
        slack_cfg = _make_slack_config()
        db = _mock_db(devices=[], slack_config=slack_cfg)

        result = await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.SYSTEM,
        )

        assert result["slack_sent"] is False
        mock_slack.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_extra_data_passed_through(self, dispatcher, mock_push, mock_slack, user_id):
        device = _make_device()
        slack_cfg = _make_slack_config()
        db = _mock_db(devices=[device], slack_config=slack_cfg)
        extra = {"alert_id": "abc-123"}

        await dispatcher.notify(
            db=db,
            user_id=user_id,
            title="Test",
            body="Body",
            notification_type=NotificationType.RULE_MATCH,
            extra_data=extra,
        )

        push_call = mock_push.send.call_args.kwargs
        assert push_call["extra_data"] == extra

        slack_call = mock_slack.send.call_args.kwargs
        assert slack_call["extra_data"] == extra
