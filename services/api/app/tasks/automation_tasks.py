"""Celery tasks for v3 smart automation features."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.alert import Alert
from app.models.device_token import DeviceToken
from app.models.digest_subscription import DigestSubscription
from app.models.follow_up_reminder import FollowUpReminder, ReminderStatus
from app.models.oauth_token import OAuthToken
from app.models.processed_message import ProcessedMessage
from app.models.proposed_event import ProposedEvent
from app.services.push_service import NotificationType, get_push_service

logger = logging.getLogger(__name__)


def _get_async_session() -> async_sessionmaker:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


# --- Follow-up reminders ---


@shared_task(name="app.tasks.automation_tasks.create_follow_up_reminder")
def create_follow_up_reminder(
    user_id: str,
    message_id: str,
    thread_id: str,
    remind_after_hours: int = 72,
):
    """Create a follow-up reminder for a sent message."""
    import uuid

    async def _create():
        session_factory = _get_async_session()
        async with session_factory() as db:
            reminder = FollowUpReminder(
                user_id=uuid.UUID(user_id),
                message_id=message_id,
                thread_id=thread_id,
                remind_after_hours=remind_after_hours,
            )
            db.add(reminder)
            await db.commit()
            logger.info("Created follow-up reminder for message %s", message_id)

    asyncio.run(_create())


@shared_task(name="app.tasks.automation_tasks.check_follow_up_reminders")
def check_follow_up_reminders():
    """Periodic task: check pending follow-up reminders past their deadline.

    For each, check if a reply exists in the thread. If no reply, trigger
    push notification and update status.
    """

    async def _check():
        settings = get_settings()
        session_factory = _get_async_session()
        async with session_factory() as db:
            now = datetime.now(timezone.utc)

            # Find pending reminders past deadline
            result = await db.execute(
                select(FollowUpReminder).where(
                    FollowUpReminder.status == ReminderStatus.PENDING,
                )
            )
            reminders = result.scalars().all()

            for reminder in reminders:
                deadline = reminder.created_at + timedelta(hours=reminder.remind_after_hours)
                if now < deadline:
                    continue

                # Check if reply exists in thread via Gmail
                has_reply = False
                try:
                    from app.services.crypto_service import get_crypto_service
                    from app.services.gmail_service import GmailService

                    oauth_result = await db.execute(
                        select(OAuthToken).where(OAuthToken.user_id == reminder.user_id)
                    )
                    oauth_token = oauth_result.scalar_one_or_none()
                    if not oauth_token:
                        continue

                    crypto = get_crypto_service(settings)
                    gmail = GmailService(settings, crypto)

                    thread = await gmail.get_thread(
                        encrypted_access_token=oauth_token.encrypted_access_token,
                        encrypted_refresh_token=oauth_token.encrypted_refresh_token,
                        thread_id=reminder.thread_id,
                    )

                    # Check if any message after the tracked one exists
                    messages = thread.get("messages", [])
                    found_original = False
                    for msg in messages:
                        if msg.get("id") == reminder.message_id:
                            found_original = True
                            continue
                        if found_original:
                            has_reply = True
                            break

                except Exception as e:
                    logger.warning(
                        "Failed to check thread for reminder %s: %s", reminder.id, e
                    )
                    continue

                if has_reply:
                    # Reply received — dismiss
                    reminder.status = ReminderStatus.DISMISSED
                    await db.flush()
                    continue

                # No reply — trigger notification
                reminder.status = ReminderStatus.TRIGGERED
                reminder.triggered_at = now
                await db.flush()

                # Get subject from processed message
                pm_result = await db.execute(
                    select(ProcessedMessage).where(
                        ProcessedMessage.user_id == reminder.user_id,
                        ProcessedMessage.message_id == reminder.message_id,
                    )
                )
                pm = pm_result.scalar_one_or_none()
                subject = pm.subject if pm else "(unknown subject)"

                # Send push notification
                devices_result = await db.execute(
                    select(DeviceToken).where(DeviceToken.user_id == reminder.user_id)
                )
                devices = devices_result.scalars().all()

                push = get_push_service(settings)
                for device in devices:
                    await push.send(
                        platform=device.platform,
                        token=device.token,
                        title="EHA: No reply received",
                        body=f"No reply to: {subject}",
                        notification_type=NotificationType.FOLLOW_UP,
                        extra_data={
                            "reminder_id": str(reminder.id),
                            "thread_id": reminder.thread_id,
                        },
                    )

            await db.commit()

    asyncio.run(_check())


# --- Meeting prep ---


@shared_task(name="app.tasks.automation_tasks.generate_meeting_prep_task")
def generate_meeting_prep_task(user_id: str, event_id: str):
    """Generate and send meeting prep summary for a specific event."""

    async def _generate():
        settings = get_settings()
        session_factory = _get_async_session()
        async with session_factory() as db:
            import uuid

            event_uuid = uuid.UUID(event_id)
            user_uuid = uuid.UUID(user_id)

            # Fetch event
            result = await db.execute(
                select(ProposedEvent).where(
                    ProposedEvent.id == event_uuid,
                    ProposedEvent.user_id == user_uuid,
                )
            )
            event = result.scalar_one_or_none()
            if not event:
                logger.info("Event %s not found for user %s", event_id, user_id)
                return

            event_data = event.event_data or {}
            title = event_data.get("title", "Meeting")
            start_dt = event_data.get("start_datetime", "")
            attendees = event_data.get("attendees", []) or []

            # Find related emails: same thread_id, from attendees, or subject keyword match
            related_conditions = []
            queries = []

            # By attendees
            if attendees:
                for attendee in attendees:
                    q = select(ProcessedMessage).where(
                        ProcessedMessage.user_id == user_uuid,
                        ProcessedMessage.from_addr.ilike(f"%{attendee}%"),
                    ).limit(5)
                    queries.append(q)

            # By subject keywords
            title_words = [w for w in title.split() if len(w) > 3]
            for word in title_words[:3]:
                q = select(ProcessedMessage).where(
                    ProcessedMessage.user_id == user_uuid,
                    ProcessedMessage.subject.ilike(f"%{word}%"),
                ).limit(5)
                queries.append(q)

            # Collect related messages (deduplicated)
            seen_ids = set()
            related_messages = []
            for q in queries:
                res = await db.execute(q)
                for pm in res.scalars().all():
                    if pm.id not in seen_ids:
                        seen_ids.add(pm.id)
                        related_messages.append({
                            "from_addr": pm.from_addr or "unknown",
                            "subject": pm.subject or "(no subject)",
                            "date": str(pm.received_at or ""),
                            "body": pm.snippet or "",
                        })

            if not related_messages:
                logger.info("No related emails found for event %s", event_id)
                return

            # Generate meeting prep via AI
            from app.services.ai_service import get_ai_service

            ai = get_ai_service(settings)
            prep = await ai.generate_meeting_prep(
                meeting_title=title,
                meeting_time=start_dt,
                attendees=attendees,
                related_emails=related_messages,
            )

            if not prep:
                logger.warning("AI meeting prep generation failed for event %s", event_id)
                return

            # Send push notification with summary
            devices_result = await db.execute(
                select(DeviceToken).where(DeviceToken.user_id == user_uuid)
            )
            devices = devices_result.scalars().all()

            push = get_push_service(settings)
            body = f"{title}: {prep.agenda_context[:200]}"
            for device in devices:
                await push.send(
                    platform=device.platform,
                    token=device.token,
                    title="EHA: Meeting Prep",
                    body=body,
                    notification_type=NotificationType.MEETING_PREP,
                    extra_data={
                        "event_id": event_id,
                        "discussion_points": str(len(prep.key_discussion_points)),
                    },
                )

            logger.info("Sent meeting prep for event %s", event_id)

    asyncio.run(_generate())


@shared_task(name="app.tasks.automation_tasks.check_upcoming_meetings")
def check_upcoming_meetings():
    """Periodic task: find confirmed events starting in 2-24 hours and generate prep summaries."""

    async def _check():
        session_factory = _get_async_session()
        async with session_factory() as db:
            now = datetime.now(timezone.utc)
            window_start = now + timedelta(hours=2)
            window_end = now + timedelta(hours=24)

            result = await db.execute(
                select(ProposedEvent).where(
                    ProposedEvent.status == "confirmed",
                )
            )
            events = result.scalars().all()

            for event in events:
                event_data = event.event_data or {}
                start_str = event_data.get("start_datetime")
                if not start_str:
                    continue
                try:
                    start_dt = datetime.fromisoformat(start_str)
                    if window_start <= start_dt <= window_end:
                        generate_meeting_prep_task.delay(
                            user_id=str(event.user_id),
                            event_id=str(event.id),
                        )
                except (ValueError, TypeError):
                    continue

    asyncio.run(_check())


# --- Digest notifications ---


@shared_task(name="app.tasks.automation_tasks.send_digest_notifications")
def send_digest_notifications():
    """Periodic task: send digest push notifications to subscribed users.

    Runs every hour. Checks which subscriptions are due based on frequency,
    day_of_week, and hour_utc.
    """

    async def _send():
        settings = get_settings()
        session_factory = _get_async_session()
        async with session_factory() as db:
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            current_dow = now.weekday()  # 0=Monday

            # Find active subscriptions due now
            result = await db.execute(
                select(DigestSubscription).where(
                    DigestSubscription.is_active == True,  # noqa: E712
                    DigestSubscription.hour_utc == current_hour,
                )
            )
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                # Check frequency constraints
                if sub.frequency == "weekly" and sub.day_of_week != current_dow:
                    continue

                # Check last_sent_at to avoid double-sends
                if sub.last_sent_at:
                    if sub.frequency == "daily":
                        if (now - sub.last_sent_at) < timedelta(hours=20):
                            continue
                    elif sub.frequency == "weekly":
                        if (now - sub.last_sent_at) < timedelta(days=6):
                            continue

                # Determine period
                if sub.frequency == "daily":
                    period_start = now - timedelta(days=1)
                else:
                    period_start = now - timedelta(weeks=1)

                since = sub.last_sent_at or period_start

                # Fetch unread alerts since last_sent_at
                alerts_result = await db.execute(
                    select(Alert).where(
                        Alert.user_id == sub.user_id,
                        Alert.created_at >= since,
                    )
                )
                alerts = alerts_result.scalars().all()

                if not alerts:
                    # Nothing to digest
                    sub.last_sent_at = now
                    await db.flush()
                    continue

                # Build alert summaries text
                alert_lines = []
                for alert in alerts:
                    # Get associated processed message
                    pm_result = await db.execute(
                        select(ProcessedMessage).where(
                            ProcessedMessage.user_id == sub.user_id,
                            ProcessedMessage.message_id == alert.message_id,
                        )
                    )
                    pm = pm_result.scalar_one_or_none()
                    subject = pm.subject if pm else "(unknown)"
                    from_addr = pm.from_addr if pm else "unknown"
                    category = pm.category if pm else "general"
                    alert_lines.append(
                        f"- [{category}] From: {from_addr} | Subject: {subject}"
                    )

                alert_text = "\n".join(alert_lines)

                # Generate AI digest
                try:
                    from app.services.ai_service import get_ai_service

                    ai = get_ai_service(settings)
                    digest = await ai.generate_digest_summary(
                        alert_summaries=alert_text,
                        alert_count=len(alerts),
                        period_start=since.isoformat(),
                    )
                except Exception as e:
                    logger.warning("Digest AI generation failed for user %s: %s", sub.user_id, e)
                    digest = None

                # Send push notification
                body = digest.summary if digest else f"You have {len(alerts)} new alerts."
                devices_result = await db.execute(
                    select(DeviceToken).where(DeviceToken.user_id == sub.user_id)
                )
                devices = devices_result.scalars().all()

                push = get_push_service(settings)
                for device in devices:
                    await push.send(
                        platform=device.platform,
                        token=device.token,
                        title=f"EHA: {'Daily' if sub.frequency == 'daily' else 'Weekly'} Digest",
                        body=body[:500],
                        notification_type=NotificationType.DIGEST,
                        extra_data={"alert_count": str(len(alerts))},
                    )

                sub.last_sent_at = now
                await db.flush()
                logger.info(
                    "Sent %s digest to user %s (%d alerts)",
                    sub.frequency, sub.user_id, len(alerts),
                )

            await db.commit()

    asyncio.run(_send())
