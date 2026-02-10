"""Event proposal routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_current_user_id, get_db
from app.models.proposed_event import EventStatus, ProposedEvent
from app.schemas.event import EventConfirmRequest, EventDismissRequest, EventProposalResponse
from app.services.ai_service import get_ai_service
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/proposed", response_model=list[EventProposalResponse])
async def list_proposed_events(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
):
    """List proposed events for the current user."""
    query = select(ProposedEvent).where(ProposedEvent.user_id == user_id).order_by(ProposedEvent.created_at.desc())

    if status_filter:
        try:
            event_status = EventStatus(status_filter)
            query = query.where(ProposedEvent.status == event_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    result = await db.execute(query)
    events = result.scalars().all()

    return [
        EventProposalResponse(
            id=str(e.id),
            message_id=e.message_id,
            event_data=e.event_data,
            status=e.status.value,
            created_at=e.created_at.isoformat(),
        )
        for e in events
    ]


@router.post("/confirm", response_model=EventProposalResponse)
async def confirm_event(
    body: EventConfirmRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Confirm a proposed event.

    After confirmation, the mobile app will write it to the device calendar.
    """
    ai = get_ai_service(settings)
    service = EventService(ai)

    event = await service.confirm_event(
        db=db,
        user_id=user_id,
        event_id=uuid.UUID(body.event_id),
    )

    if not event:
        raise HTTPException(status_code=404, detail="Proposed event not found")

    from app.metrics import events_proposed_total

    events_proposed_total.labels(action="confirmed").inc()

    return EventProposalResponse(
        id=str(event.id),
        message_id=event.message_id,
        event_data=event.event_data,
        status=event.status.value,
        created_at=event.created_at.isoformat(),
    )


@router.post("/dismiss", response_model=EventProposalResponse)
async def dismiss_event(
    body: EventDismissRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Dismiss a proposed event."""
    ai = get_ai_service(settings)
    service = EventService(ai)

    event = await service.dismiss_event(
        db=db,
        user_id=user_id,
        event_id=uuid.UUID(body.event_id),
    )

    if not event:
        raise HTTPException(status_code=404, detail="Proposed event not found")

    from app.metrics import events_proposed_total

    events_proposed_total.labels(action="dismissed").inc()

    return EventProposalResponse(
        id=str(event.id),
        message_id=event.message_id,
        event_data=event.event_data,
        status=event.status.value,
        created_at=event.created_at.isoformat(),
    )
