"""Draft routes for creating Gmail drafts."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_current_user_id, get_db
from app.models.draft import Draft
from app.schemas.draft import DraftCreateRequest, DraftResponse
from app.services.crypto_service import get_crypto_service
from app.services.draft_service import DraftService
from app.services.gmail_service import get_gmail_service

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("", response_model=DraftResponse, status_code=201)
async def create_draft(
    body: DraftCreateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Create a Gmail draft from an AI-generated proposal.

    The draft is created in Gmail's draft folder.
    EHA NEVER sends emails automatically — the user must send it themselves.
    """
    crypto = get_crypto_service(settings)
    gmail = get_gmail_service(settings, crypto)
    service = DraftService(gmail)

    try:
        draft = await service.create_draft(
            db=db,
            user_id=user_id,
            message_id=body.message_id,
            to=body.to,
            subject=body.subject,
            body=body.body,
            tone=body.tone,
            thread_id=body.thread_id,
            in_reply_to=body.in_reply_to,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.metrics import drafts_created_total

    drafts_created_total.inc()

    return DraftResponse(
        id=str(draft.id),
        message_id=draft.message_id,
        gmail_draft_id=draft.gmail_draft_id,
        content_preview=draft.content_preview,
        tone=draft.tone,
        created_at=draft.created_at.isoformat(),
    )


@router.get("", response_model=list[DraftResponse])
async def list_drafts(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """List drafts created by the current user."""
    result = await db.execute(
        select(Draft).where(Draft.user_id == user_id).order_by(Draft.created_at.desc()).limit(limit)
    )
    drafts = result.scalars().all()
    return [
        DraftResponse(
            id=str(d.id),
            message_id=d.message_id,
            gmail_draft_id=d.gmail_draft_id,
            content_preview=d.content_preview,
            tone=d.tone,
            created_at=d.created_at.isoformat(),
        )
        for d in drafts
    ]
