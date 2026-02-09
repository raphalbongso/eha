"""Leave time / travel advisory tasks — v2.

Calculates optimal departure times and sends "time to leave" notifications.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.proposed_event import ProposedEvent
from app.models.user_preference import UserPreference
from app.services.push_service import NotificationType, get_push_service
from app.services.route_service import get_route_provider

logger = logging.getLogger(__name__)


def _get_async_session() -> async_sessionmaker:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _calculate_and_notify(user_id: str, event_id: str) -> None:
    """Core logic: fetch event + prefs, query route, schedule notification."""
    settings = get_settings()
    route_provider = get_route_provider(settings)
    if route_provider is None:
        logger.info("Route provider not configured; skipping leave-time for event %s", event_id)
        return

    session_factory = _get_async_session()
    async with session_factory() as db:
        # Fetch event
        result = await db.execute(select(ProposedEvent).where(ProposedEvent.id == event_id))
        event = result.scalar_one_or_none()
        if not event or event.status != "confirmed":
            logger.info("Event %s not found or not confirmed; skipping", event_id)
            return

        event_data = event.event_data or {}
        location = event_data.get("location")
        start_str = event_data.get("start_datetime")
        if not location or not start_str:
            logger.info("Event %s missing location or start_datetime; skipping", event_id)
            return

        try:
            start_dt = datetime.fromisoformat(start_str)
        except ValueError:
            logger.warning("Invalid start_datetime for event %s: %s", event_id, start_str)
            return

        # Fetch user preferences
        result = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
        pref = result.scalar_one_or_none()
        if not pref or not pref.home_address:
            logger.info("User %s has no home address configured; skipping", user_id[:8])
            return

        origin = pref.home_address
        mode = pref.preferred_transport_mode or "driving"

        # Calculate travel time
        try:
            estimate = await route_provider.get_travel_time(
                origin=origin,
                destination=location,
                mode=mode,
            )
        except Exception as e:
            logger.error("Route calculation failed for event %s: %s", event_id, e)
            return

        # Calculate departure time (event start - travel time - 15 min buffer)
        buffer_minutes = 15
        departure_dt = start_dt - timedelta(minutes=estimate.duration_minutes + buffer_minutes)
        now = datetime.now(timezone.utc)

        if departure_dt <= now:
            logger.info("Departure time already passed for event %s; sending immediate alert", event_id)

        # Send push notification
        from app.models.device_token import DeviceToken

        result = await db.execute(select(DeviceToken).where(DeviceToken.user_id == user_id))
        tokens = result.scalars().all()

        if not tokens:
            logger.info("No device tokens for user %s", user_id[:8])
            return

        push_service = get_push_service(settings)
        title_text = event_data.get("title", "Your event")
        travel_mins = int(estimate.duration_minutes)
        body = f"Leave in {travel_mins} min for {title_text} ({estimate.distance_km} km by {mode})"

        for dt in tokens:
            await push_service.send(
                platform=dt.platform,
                token=dt.token,
                title="Time to Leave",
                body=body,
                notification_type=NotificationType.SYSTEM,
                extra_data={
                    "event_id": event_id,
                    "travel_minutes": str(travel_mins),
                    "departure_time": departure_dt.isoformat(),
                },
            )

        logger.info("Sent leave-time notification for event %s (travel=%d min)", event_id, travel_mins)


@shared_task(name="app.tasks.leave_time_tasks.calculate_leave_time")
def calculate_leave_time(user_id: str, event_id: str):
    """Calculate when user should leave for an event and send notification.

    1. Fetch event details (location, start time)
    2. Fetch user preferences (home/work address, transport mode)
    3. Query RouteProvider for travel time
    4. Send push notification with departure advisory
    """
    asyncio.run(_calculate_and_notify(user_id, event_id))


@shared_task(name="app.tasks.leave_time_tasks.check_upcoming_events")
def check_upcoming_events():
    """Periodic task: check for confirmed events starting within 3 hours.

    For each upcoming event, enqueue a calculate_leave_time task.
    """

    async def _check():
        session_factory = _get_async_session()
        async with session_factory() as db:
            now = datetime.now(timezone.utc)
            window = now + timedelta(hours=3)

            # Find confirmed events starting within the window
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
                    if now <= start_dt <= window:
                        calculate_leave_time.delay(
                            user_id=str(event.user_id),
                            event_id=str(event.id),
                        )
                except (ValueError, TypeError):
                    continue

    asyncio.run(_check())
