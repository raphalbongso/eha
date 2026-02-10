"""Unified notification dispatcher for push + Slack channels."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.device_token import DeviceToken
from app.models.slack_config import SlackConfig
from app.services.crypto_service import CryptoService, get_crypto_service
from app.services.push_service import NotificationType, PushService, get_push_service
from app.services.slack_service import SlackService, get_slack_service

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Orchestrates sending notifications across push and Slack channels."""

    def __init__(
        self,
        push_service: PushService,
        slack_service: SlackService,
        crypto_service: CryptoService,
    ) -> None:
        self._push = push_service
        self._slack = slack_service
        self._crypto = crypto_service

    async def notify(
        self,
        db: AsyncSession,
        user_id,
        title: str,
        body: str,
        notification_type: NotificationType,
        extra_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a notification to all configured channels for a user.

        Returns a dict summarising what was sent:
            {"push_sent": int, "push_failed": int, "slack_sent": bool | None}
        """
        result: dict[str, Any] = {"push_sent": 0, "push_failed": 0, "slack_sent": None}

        # --- Push notifications ---
        devices_result = await db.execute(
            select(DeviceToken).where(DeviceToken.user_id == user_id)
        )
        devices = devices_result.scalars().all()

        for device in devices:
            success = await self._push.send(
                platform=device.platform,
                token=device.token,
                title=title,
                body=body,
                notification_type=notification_type,
                extra_data=extra_data,
            )
            if success:
                result["push_sent"] += 1
            else:
                result["push_failed"] += 1

        # --- Slack ---
        slack_result = await db.execute(
            select(SlackConfig).where(SlackConfig.user_id == user_id)
        )
        slack_config = slack_result.scalar_one_or_none()

        if slack_config and slack_config.is_enabled:
            # Check if this notification type is allowed
            allowed_types = slack_config.enabled_notification_types or []
            type_allowed = (
                len(allowed_types) == 0
                or notification_type.value in allowed_types
            )

            if type_allowed:
                try:
                    webhook_url = self._crypto.decrypt(slack_config.webhook_url)
                    result["slack_sent"] = await self._slack.send(
                        webhook_url=webhook_url,
                        title=title,
                        body=body,
                        notification_type=notification_type,
                        extra_data=extra_data,
                    )
                except Exception as e:
                    logger.error("Slack dispatch failed for user %s: %s", user_id, e)
                    result["slack_sent"] = False

        return result


def get_notification_dispatcher(settings: Settings) -> NotificationDispatcher:
    """Factory that wires up a NotificationDispatcher with its dependencies."""
    return NotificationDispatcher(
        push_service=get_push_service(settings),
        slack_service=get_slack_service(),
        crypto_service=get_crypto_service(settings),
    )
