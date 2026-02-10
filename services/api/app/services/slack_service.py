"""Slack notification service via incoming webhooks."""

import logging

import httpx

from app.services.push_service import NotificationType

logger = logging.getLogger(__name__)

# Slack attachment color per notification type
_COLOR_MAP: dict[str, str] = {
    NotificationType.RULE_MATCH: "#E74C3C",      # red
    NotificationType.FOLLOW_UP: "#F39C12",        # orange
    NotificationType.DIGEST: "#3498DB",            # blue
    NotificationType.MEETING_PREP: "#9B59B6",      # purple
    NotificationType.EVENT_PROPOSAL: "#2ECC71",    # green
    NotificationType.SYSTEM: "#95A5A6",            # gray
}

# Slack blocks have a 3000-char text limit
_MAX_BODY_LENGTH = 3000


class SlackService:
    """Send notifications to Slack via incoming webhooks."""

    async def send(
        self,
        webhook_url: str,
        title: str,
        body: str,
        notification_type: str | NotificationType = NotificationType.SYSTEM,
        extra_data: dict | None = None,
    ) -> bool:
        """Post a formatted message to a Slack webhook.

        Returns True on success, False on failure.
        """
        if isinstance(notification_type, NotificationType):
            type_str = notification_type.value
        else:
            type_str = notification_type

        color = _COLOR_MAP.get(type_str, _COLOR_MAP[NotificationType.SYSTEM])

        # Truncate body to Slack limit
        truncated_body = body[:_MAX_BODY_LENGTH]
        if len(body) > _MAX_BODY_LENGTH:
            truncated_body = truncated_body[: _MAX_BODY_LENGTH - 3] + "..."

        payload = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": title[:150],
                                "emoji": True,
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": truncated_body,
                            },
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"Type: *{type_str}*",
                                },
                            ],
                        },
                    ],
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(webhook_url, json=payload)
                if response.status_code == 200:
                    logger.info("Slack notification sent: %s", title)
                    return True
                else:
                    logger.warning(
                        "Slack webhook returned %d: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    return False
        except httpx.TimeoutException:
            logger.error("Slack webhook timed out for: %s", title)
            return False
        except Exception as e:
            logger.error("Slack notification failed: %s", e)
            return False


def get_slack_service() -> SlackService:
    return SlackService()
