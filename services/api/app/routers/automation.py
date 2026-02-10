"""Automation endpoints for v3 smart features."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_id, get_db
from app.models.alert import Alert
from app.models.digest_subscription import DigestSubscription
from app.models.follow_up_reminder import FollowUpReminder, ReminderStatus
from app.models.processed_message import ProcessedMessage
from app.models.proposed_event import ProposedEvent
from app.schemas.automation import (
    DigestPreviewResponse,
    DigestSubscriptionCreate,
    DigestSubscriptionResponse,
    DigestSubscriptionUpdate,
    FollowUpReminderCreate,
    FollowUpReminderList,
    FollowUpReminderResponse,
    MeetingPrepResponse,
)

router = APIRouter(prefix="/automation", tags=["automation"])


# --- Follow-up reminders ---


@router.post("/follow-up", response_model=FollowUpReminderResponse, status_code=201)
async def create_follow_up(
    body: FollowUpReminderCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a follow-up reminder for a sent message."""
    reminder = FollowUpReminder(
        user_id=user_id,
        message_id=body.message_id,
        thread_id=body.thread_id,
        remind_after_hours=body.remind_after_hours,
    )
    db.add(reminder)
    await db.flush()
    return FollowUpReminderResponse.model_validate(reminder)


@router.get("/follow-ups", response_model=FollowUpReminderList)
async def list_follow_ups(
    status_filter: str | None = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List user's follow-up reminders, optionally filtered by status."""
    query = select(FollowUpReminder).where(FollowUpReminder.user_id == user_id)
    if status_filter:
        try:
            rs = ReminderStatus(status_filter)
            query = query.where(FollowUpReminder.status == rs)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status_filter}. Use pending, triggered, or dismissed.",
            )
    query = query.order_by(FollowUpReminder.created_at.desc())
    result = await db.execute(query)
    reminders = result.scalars().all()
    return FollowUpReminderList(
        reminders=[FollowUpReminderResponse.model_validate(r) for r in reminders],
        total=len(reminders),
    )


@router.delete("/follow-up/{reminder_id}", status_code=204)
async def dismiss_follow_up(
    reminder_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss a follow-up reminder."""
    result = await db.execute(
        select(FollowUpReminder).where(
            FollowUpReminder.id == reminder_id,
            FollowUpReminder.user_id == user_id,
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder.status = ReminderStatus.DISMISSED
    await db.flush()


# --- Meeting prep ---


@router.post("/meeting-prep/{event_id}", response_model=MeetingPrepResponse)
async def generate_meeting_prep(
    event_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """On-demand meeting prep summary for a specific event."""
    from app.config import get_settings
    from app.services.ai_service import get_ai_service

    # Fetch event
    result = await db.execute(
        select(ProposedEvent).where(
            ProposedEvent.id == event_id,
            ProposedEvent.user_id == user_id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event_data = event.event_data or {}
    title = event_data.get("title", "Meeting")
    start_dt = event_data.get("start_datetime", "")
    attendees = event_data.get("attendees", []) or []

    # Find related emails
    queries = []
    if attendees:
        for attendee in attendees:
            queries.append(
                select(ProcessedMessage).where(
                    ProcessedMessage.user_id == user_id,
                    ProcessedMessage.from_addr.ilike(f"%{attendee}%"),
                ).limit(5)
            )
    title_words = [w for w in title.split() if len(w) > 3]
    for word in title_words[:3]:
        queries.append(
            select(ProcessedMessage).where(
                ProcessedMessage.user_id == user_id,
                ProcessedMessage.subject.ilike(f"%{word}%"),
            ).limit(5)
        )

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

    settings = get_settings()
    ai = get_ai_service(settings)
    prep = await ai.generate_meeting_prep(
        meeting_title=title,
        meeting_time=start_dt,
        attendees=attendees,
        related_emails=related_messages,
    )

    if not prep:
        raise HTTPException(status_code=500, detail="Failed to generate meeting prep")

    return MeetingPrepResponse(
        event_id=str(event_id),
        agenda_context=prep.agenda_context,
        key_discussion_points=prep.key_discussion_points,
        open_action_items=prep.open_action_items,
        relevant_attachments=prep.relevant_attachments,
    )


# --- Digest subscriptions ---


@router.post("/digest", response_model=DigestSubscriptionResponse, status_code=201)
async def create_or_update_digest(
    body: DigestSubscriptionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create or update digest subscription."""
    result = await db.execute(
        select(DigestSubscription).where(DigestSubscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()

    if sub:
        sub.frequency = body.frequency
        sub.day_of_week = body.day_of_week
        sub.hour_utc = body.hour_utc
        sub.is_active = True
    else:
        sub = DigestSubscription(
            user_id=user_id,
            frequency=body.frequency,
            day_of_week=body.day_of_week,
            hour_utc=body.hour_utc,
        )
        db.add(sub)

    await db.flush()
    return DigestSubscriptionResponse.model_validate(sub)


@router.get("/digest", response_model=DigestSubscriptionResponse)
async def get_digest(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get user's digest subscription."""
    result = await db.execute(
        select(DigestSubscription).where(DigestSubscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No digest subscription found")
    return DigestSubscriptionResponse.model_validate(sub)


@router.delete("/digest", status_code=204)
async def disable_digest(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Disable digest subscription."""
    result = await db.execute(
        select(DigestSubscription).where(DigestSubscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No digest subscription found")
    sub.is_active = False
    await db.flush()


@router.post("/digest/preview", response_model=DigestPreviewResponse)
async def preview_digest(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate an on-demand digest preview."""
    from app.config import get_settings
    from app.services.ai_service import get_ai_service

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=1)

    # Fetch recent alerts
    alerts_result = await db.execute(
        select(Alert).where(
            Alert.user_id == user_id,
            Alert.created_at >= period_start,
        )
    )
    alerts = alerts_result.scalars().all()

    if not alerts:
        return DigestPreviewResponse(
            summary="No alerts in the last 24 hours.",
            alert_count=0,
            highlights=[],
            period_start=period_start,
            period_end=now,
        )

    # Build alert summaries
    alert_lines = []
    for alert in alerts:
        pm_result = await db.execute(
            select(ProcessedMessage).where(
                ProcessedMessage.user_id == user_id,
                ProcessedMessage.message_id == alert.message_id,
            )
        )
        pm = pm_result.scalar_one_or_none()
        subject = pm.subject if pm else "(unknown)"
        from_addr = pm.from_addr if pm else "unknown"
        category = pm.category if pm else "general"
        alert_lines.append(f"- [{category}] From: {from_addr} | Subject: {subject}")

    alert_text = "\n".join(alert_lines)

    settings = get_settings()
    ai = get_ai_service(settings)
    digest = await ai.generate_digest_summary(
        alert_summaries=alert_text,
        alert_count=len(alerts),
        period_start=period_start.isoformat(),
    )

    if digest:
        return DigestPreviewResponse(
            summary=digest.summary,
            alert_count=len(alerts),
            highlights=digest.highlights,
            period_start=period_start,
            period_end=now,
        )

    return DigestPreviewResponse(
        summary=f"You have {len(alerts)} alerts from the last 24 hours.",
        alert_count=len(alerts),
        highlights=[],
        period_start=period_start,
        period_end=now,
    )
