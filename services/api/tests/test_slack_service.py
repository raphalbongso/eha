"""Unit tests for SlackService."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.push_service import NotificationType
from app.services.slack_service import SlackService, _MAX_BODY_LENGTH


@pytest.fixture
def slack_service():
    return SlackService()


@pytest.fixture
def webhook_url():
    return "https://hooks.slack.com/services/T00/B00/xxxx"


class TestSlackServiceSend:
    """Tests for SlackService.send()."""

    @pytest.mark.asyncio
    async def test_successful_send(self, slack_service, webhook_url):
        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await slack_service.send(
                webhook_url=webhook_url,
                title="Test Alert",
                body="Something happened",
                notification_type=NotificationType.RULE_MATCH,
            )

        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == webhook_url
        payload = call_args[1]["json"]
        assert "attachments" in payload
        # Check color is red for RULE_MATCH
        assert payload["attachments"][0]["color"] == "#E74C3C"

    @pytest.mark.asyncio
    async def test_non_200_returns_false(self, slack_service, webhook_url):
        mock_response = MagicMock(status_code=403, text="invalid_token")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await slack_service.send(
                webhook_url=webhook_url,
                title="Test",
                body="Body",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_timeout_returns_false(self, slack_service, webhook_url):
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timed out")

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await slack_service.send(
                webhook_url=webhook_url,
                title="Test",
                body="Body",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_generic_exception_returns_false(self, slack_service, webhook_url):
        mock_client = AsyncMock()
        mock_client.post.side_effect = ConnectionError("connection refused")

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await slack_service.send(
                webhook_url=webhook_url,
                title="Test",
                body="Body",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_block_kit_format(self, slack_service, webhook_url):
        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await slack_service.send(
                webhook_url=webhook_url,
                title="My Title",
                body="My body text",
                notification_type=NotificationType.DIGEST,
            )

        payload = mock_client.post.call_args[1]["json"]
        attachment = payload["attachments"][0]
        blocks = attachment["blocks"]

        # header block
        assert blocks[0]["type"] == "header"
        assert blocks[0]["text"]["text"] == "My Title"

        # body section
        assert blocks[1]["type"] == "section"
        assert blocks[1]["text"]["text"] == "My body text"

        # context with type
        assert blocks[2]["type"] == "context"
        assert "DIGEST" in blocks[2]["elements"][0]["text"]

        # color for digest = blue
        assert attachment["color"] == "#3498DB"

    @pytest.mark.asyncio
    async def test_body_truncation(self, slack_service, webhook_url):
        long_body = "x" * 5000
        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await slack_service.send(
                webhook_url=webhook_url,
                title="Long",
                body=long_body,
            )

        payload = mock_client.post.call_args[1]["json"]
        body_text = payload["attachments"][0]["blocks"][1]["text"]["text"]
        assert len(body_text) <= _MAX_BODY_LENGTH
        assert body_text.endswith("...")

    @pytest.mark.asyncio
    async def test_color_per_notification_type(self, slack_service, webhook_url):
        expected_colors = {
            NotificationType.RULE_MATCH: "#E74C3C",
            NotificationType.FOLLOW_UP: "#F39C12",
            NotificationType.DIGEST: "#3498DB",
            NotificationType.MEETING_PREP: "#9B59B6",
            NotificationType.EVENT_PROPOSAL: "#2ECC71",
            NotificationType.SYSTEM: "#95A5A6",
        }

        for ntype, expected_color in expected_colors.items():
            mock_response = MagicMock(status_code=200)
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response

            with patch("app.services.slack_service.httpx.AsyncClient") as mock_cls:
                mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

                await slack_service.send(
                    webhook_url=webhook_url,
                    title="Test",
                    body="Body",
                    notification_type=ntype,
                )

            payload = mock_client.post.call_args[1]["json"]
            actual_color = payload["attachments"][0]["color"]
            assert actual_color == expected_color, f"Expected {expected_color} for {ntype}, got {actual_color}"

    @pytest.mark.asyncio
    async def test_string_notification_type(self, slack_service, webhook_url):
        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await slack_service.send(
                webhook_url=webhook_url,
                title="Test",
                body="Body",
                notification_type="RULE_MATCH",
            )

        assert result is True
