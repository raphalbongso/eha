"""Push notification service for APNs and FCM."""

import json
import logging
from enum import Enum
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    RULE_MATCH = "RULE_MATCH"
    EVENT_PROPOSAL = "EVENT_PROPOSAL"
    SYSTEM = "SYSTEM"


class PushService:
    """Send push notifications to iOS (APNs) and Android (FCM) devices."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fcm_app = None
        self._apns_client = None

    def _init_fcm(self):
        """Initialize Firebase Admin SDK (lazy)."""
        if self._fcm_app is not None:
            return
        if not self._settings.fcm_credentials_json:
            logger.warning("FCM credentials not configured; push to Android disabled")
            return
        try:
            import firebase_admin
            from firebase_admin import credentials

            cred = credentials.Certificate(self._settings.fcm_credentials_json)
            self._fcm_app = firebase_admin.initialize_app(cred)
        except Exception as e:
            logger.error("Failed to initialize FCM: %s", e)

    async def send_fcm(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> bool:
        """Send a push notification via FCM."""
        self._init_fcm()
        if self._fcm_app is None:
            logger.warning("FCM not initialized; skipping push")
            return False

        try:
            from firebase_admin import messaging

            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                token=token,
            )
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: messaging.send(message)
            )
            logger.info("FCM sent: %s", result)
            return True
        except Exception as e:
            logger.error("FCM send failed: %s", e)
            return False

    async def send_apns(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> bool:
        """Send a push notification via APNs."""
        if not self._settings.apns_key_path:
            logger.warning("APNs not configured; skipping push")
            return False

        try:
            from apns2.client import APNsClient, NotificationPriority
            from apns2.payload import Payload

            payload = Payload(alert={"title": title, "body": body}, custom=data or {})
            client = APNsClient(
                self._settings.apns_key_path,
                use_sandbox=self._settings.app_env != "production",
            )

            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.send_notification(
                    token,
                    payload,
                    self._settings.apns_bundle_id,
                    priority=NotificationPriority.Immediate,
                ),
            )
            logger.info("APNs sent to token=%s...", token[:8])
            return True
        except Exception as e:
            logger.error("APNs send failed: %s", e)
            return False

    async def send(
        self,
        platform: str,
        token: str,
        title: str,
        body: str,
        notification_type: NotificationType,
        extra_data: dict[str, Any] | None = None,
    ) -> bool:
        """Send a push notification to the appropriate platform."""
        data = {
            "type": notification_type.value,
            **(extra_data or {}),
        }
        # Ensure all values are strings for FCM
        str_data = {k: str(v) for k, v in data.items()}

        if platform == "android":
            return await self.send_fcm(token, title, body, str_data)
        elif platform == "ios":
            return await self.send_apns(token, title, body, str_data)
        else:
            logger.warning("Unknown platform: %s", platform)
            return False


def get_push_service(settings: Settings) -> PushService:
    return PushService(settings)
