"""Celery tasks for push notifications."""

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import delete, select

from app.config import get_settings
from app.models.device_token import DeviceToken
from app.services.push_service import NotificationType, PushService

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Create a synchronous DB session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(sync_url)
    return sessionmaker(bind=engine)()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    name="app.tasks.notification_tasks.send_push_for_alert",
)
def send_push_for_alert(
    self,
    user_id: str,
    alert_id: str,
    subject: str,
    from_addr: str,
    rule_name: str,
):
    """Send push notifications for a rule match alert."""
    import asyncio
    import uuid

    settings = get_settings()
    session = _get_sync_session()

    try:
        user_uuid = uuid.UUID(user_id)

        # Get all device tokens for this user
        devices = session.execute(
            select(DeviceToken).where(DeviceToken.user_id == user_uuid)
        ).scalars().all()

        if not devices:
            logger.debug("No device tokens for user=%s", user_id)
            return

        push = PushService(settings)
        title = f"EHA: {rule_name}"
        body = f"From: {from_addr}\n{subject}"

        loop = asyncio.new_event_loop()
        try:
            for device in devices:
                success = loop.run_until_complete(
                    push.send(
                        platform=device.platform,
                        token=device.token,
                        title=title,
                        body=body,
                        notification_type=NotificationType.RULE_MATCH,
                        extra_data={
                            "alert_id": alert_id,
                            "message_subject": subject,
                        },
                    )
                )
                if success:
                    device.last_used = datetime.now(timezone.utc)

            session.commit()
        finally:
            loop.close()

    except Exception as e:
        session.rollback()
        logger.error("Push notification failed: %s", e)
        raise
    finally:
        session.close()


@shared_task(
    bind=True,
    max_retries=2,
    name="app.tasks.notification_tasks.send_event_proposal_push",
)
def send_event_proposal_push(
    self,
    user_id: str,
    event_title: str,
    confidence: float,
):
    """Send push notification for a proposed calendar event."""
    import asyncio
    import uuid

    settings = get_settings()
    session = _get_sync_session()

    try:
        user_uuid = uuid.UUID(user_id)
        devices = session.execute(
            select(DeviceToken).where(DeviceToken.user_id == user_uuid)
        ).scalars().all()

        if not devices:
            return

        push = PushService(settings)
        confidence_note = " (low confidence)" if confidence < 0.5 else ""
        title = "EHA: New event detected"
        body = f"{event_title}{confidence_note}"

        loop = asyncio.new_event_loop()
        try:
            for device in devices:
                loop.run_until_complete(
                    push.send(
                        platform=device.platform,
                        token=device.token,
                        title=title,
                        body=body,
                        notification_type=NotificationType.EVENT_PROPOSAL,
                        extra_data={"event_title": event_title},
                    )
                )
        finally:
            loop.close()

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Event push failed: %s", e)
        raise
    finally:
        session.close()


@shared_task(name="app.tasks.notification_tasks.cleanup_stale_device_tokens")
def cleanup_stale_device_tokens():
    """Remove device tokens not used in 90 days."""
    session = _get_sync_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        result = session.execute(
            delete(DeviceToken).where(
                DeviceToken.last_used < cutoff,
                DeviceToken.last_used.isnot(None),
            )
        )
        session.commit()
        logger.info("Cleaned up %d stale device tokens", result.rowcount)
    except Exception as e:
        session.rollback()
        logger.error("Cleanup failed: %s", e)
    finally:
        session.close()
