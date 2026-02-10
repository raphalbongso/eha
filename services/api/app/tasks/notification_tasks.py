"""Celery tasks for push notifications."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.device_token import DeviceToken
from app.services.notification_dispatcher import get_notification_dispatcher
from app.services.push_service import NotificationType

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Create a synchronous DB session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(sync_url)
    return sessionmaker(bind=engine)()


def _get_async_session() -> async_sessionmaker:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


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
    """Send notifications (push + Slack) for a rule match alert."""
    import uuid

    async def _send():
        settings = get_settings()
        dispatcher = get_notification_dispatcher(settings)
        session_factory = _get_async_session()
        async with session_factory() as db:
            user_uuid = uuid.UUID(user_id)
            title = f"EHA: {rule_name}"
            body = f"From: {from_addr}\n{subject}"

            await dispatcher.notify(
                db=db,
                user_id=user_uuid,
                title=title,
                body=body,
                notification_type=NotificationType.RULE_MATCH,
                extra_data={
                    "alert_id": alert_id,
                    "message_subject": subject,
                },
            )

            from app.metrics import notifications_sent_total

            notifications_sent_total.labels(type="rule_match").inc()

            await db.commit()

    asyncio.run(_send())


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
    """Send notifications (push + Slack) for a proposed calendar event."""
    import uuid

    async def _send():
        settings = get_settings()
        dispatcher = get_notification_dispatcher(settings)
        session_factory = _get_async_session()
        async with session_factory() as db:
            user_uuid = uuid.UUID(user_id)
            confidence_note = " (low confidence)" if confidence < 0.5 else ""
            title = "EHA: New event detected"
            body = f"{event_title}{confidence_note}"

            await dispatcher.notify(
                db=db,
                user_id=user_uuid,
                title=title,
                body=body,
                notification_type=NotificationType.EVENT_PROPOSAL,
                extra_data={"event_title": event_title},
            )

            from app.metrics import notifications_sent_total

            notifications_sent_total.labels(type="event_proposal").inc()

            await db.commit()

    asyncio.run(_send())


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
