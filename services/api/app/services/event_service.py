"""Event extraction and proposal service."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proposed_event import EventStatus, ProposedEvent
from app.services.ai_service import AIService
from app.services.audit_service import write_audit_log

logger = logging.getLogger(__name__)


class EventService:
    """Service for extracting and managing event proposals."""

    def __init__(self, ai_service: AIService) -> None:
        self._ai = ai_service

    async def extract_and_propose(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        message_id: str,
        from_addr: str,
        subject: str,
        date: str,
        body: str,
    ) -> ProposedEvent | None:
        """Extract event from email and create a proposal.

        Returns None if no event was detected or confidence is too low.
        """
        event = await self._ai.extract_event(
            from_addr=from_addr,
            subject=subject,
            date=date,
            body=body,
        )

        if event is None:
            return None

        if event.title is None:
            return None

        # Store proposal
        proposed = ProposedEvent(
            user_id=user_id,
            message_id=message_id,
            event_data={
                "title": event.title,
                "start_datetime": event.start_datetime,
                "end_datetime": event.end_datetime,
                "duration_minutes": event.duration_minutes,
                "location": event.location,
                "attendees": event.attendees,
                "confidence": event.confidence,
                "source_message_id": message_id,
            },
            status=EventStatus.PROPOSED,
        )
        db.add(proposed)
        await db.flush()

        await write_audit_log(
            db=db,
            user_id=user_id,
            action="event.proposed",
            entity_type="proposed_event",
            entity_id=str(proposed.id),
            metadata={"confidence": event.confidence, "title": event.title},
        )

        logger.info(
            "Event proposed for user=%s: %s (confidence=%.2f)",
            user_id,
            event.title,
            event.confidence,
        )
        return proposed

    async def confirm_event(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> ProposedEvent | None:
        """Mark a proposed event as confirmed (user will add to device calendar)."""
        from sqlalchemy import select

        result = await db.execute(
            select(ProposedEvent).where(
                ProposedEvent.id == event_id,
                ProposedEvent.user_id == user_id,
                ProposedEvent.status == EventStatus.PROPOSED,
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            return None

        event.status = EventStatus.CONFIRMED
        await db.flush()

        await write_audit_log(
            db=db,
            user_id=user_id,
            action="event.confirmed",
            entity_type="proposed_event",
            entity_id=str(event.id),
        )
        return event

    async def dismiss_event(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> ProposedEvent | None:
        """Dismiss a proposed event."""
        from sqlalchemy import select

        result = await db.execute(
            select(ProposedEvent).where(
                ProposedEvent.id == event_id,
                ProposedEvent.user_id == user_id,
                ProposedEvent.status == EventStatus.PROPOSED,
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            return None

        event.status = EventStatus.DISMISSED
        await db.flush()

        await write_audit_log(
            db=db,
            user_id=user_id,
            action="event.dismissed",
            entity_type="proposed_event",
            entity_id=str(event.id),
        )
        return event
