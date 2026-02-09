"""Alert routes for in-app inbox."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.dependencies import get_current_user_id, get_db
from app.models.alert import Alert
from app.models.processed_message import ProcessedMessage
from app.schemas.alert import AlertMarkReadRequest, AlertResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List alerts for the current user."""
    query = (
        select(Alert)
        .where(Alert.user_id == user_id)
        .options(joinedload(Alert.rule))
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if unread_only:
        query = query.where(Alert.read == False)  # noqa: E712

    result = await db.execute(query)
    alerts = result.scalars().unique().all()

    # Fetch associated message metadata for each alert
    message_ids = [a.message_id for a in alerts]
    msg_result = await db.execute(
        select(ProcessedMessage).where(
            ProcessedMessage.user_id == user_id,
            ProcessedMessage.message_id.in_(message_ids),
        )
    )
    messages_by_id = {m.message_id: m for m in msg_result.scalars().all()}

    responses = []
    for alert in alerts:
        msg = messages_by_id.get(alert.message_id)
        responses.append(
            AlertResponse(
                id=str(alert.id),
                message_id=alert.message_id,
                rule_id=str(alert.rule_id) if alert.rule_id else None,
                rule_name=alert.rule.name if alert.rule else None,
                read=alert.read,
                created_at=alert.created_at.isoformat(),
                subject=msg.subject if msg else None,
                from_addr=msg.from_addr if msg else None,
                snippet=msg.snippet if msg else None,
            )
        )
    return responses


@router.post("/mark-read")
async def mark_alerts_read(
    body: AlertMarkReadRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Mark alerts as read."""
    alert_uuids = [uuid.UUID(aid) for aid in body.alert_ids]
    await db.execute(
        update(Alert)
        .where(Alert.user_id == user_id, Alert.id.in_(alert_uuids))
        .values(read=True)
    )
    return {"status": "ok", "marked": len(alert_uuids)}
