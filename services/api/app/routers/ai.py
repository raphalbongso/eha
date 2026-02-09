"""AI routes: summarize, generate drafts, extract events."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_current_user_id, get_db
from app.models.oauth_token import OAuthToken
from app.schemas.draft import AIExtractEventRequest, AIGenerateDraftsRequest, AISummarizeRequest, SummaryResponse
from app.schemas.event import EventProposalResponse
from app.services.ai_service import get_ai_service
from app.services.crypto_service import get_crypto_service
from app.services.event_service import EventService
from app.services.gmail_parser import parse_gmail_message
from app.services.gmail_service import get_gmail_service

router = APIRouter(prefix="/ai", tags=["ai"])


async def _fetch_email_content(
    db: AsyncSession,
    user_id: uuid.UUID,
    message_id: str,
    settings: Settings,
) -> dict:
    """Fetch email content from Gmail for AI processing.

    The full body is fetched transiently and NOT stored permanently.
    """
    # Get OAuth tokens
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    crypto = get_crypto_service(settings)
    gmail = get_gmail_service(settings, crypto)

    # Fetch full message from Gmail
    raw_msg = await gmail.get_message(
        encrypted_access_token=token.encrypted_access_token,
        encrypted_refresh_token=token.encrypted_refresh_token,
        message_id=message_id,
    )

    parsed = parse_gmail_message(raw_msg)

    return {
        "from_addr": parsed.from_addr or "unknown",
        "subject": parsed.subject or "(no subject)",
        "date": parsed.received_at.isoformat() if parsed.received_at else "unknown",
        "body": parsed.body_text or parsed.snippet or "",
    }


@router.post("/summarize", response_model=SummaryResponse)
async def summarize_email(
    body: AISummarizeRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Summarize an email using AI."""
    email = await _fetch_email_content(db, user_id, body.message_id, settings)
    ai = get_ai_service(settings)

    summary = await ai.summarize(**email)
    if summary is None:
        raise HTTPException(status_code=500, detail="AI summarization failed")

    return SummaryResponse(
        summary=summary.summary,
        action_items=summary.action_items,
        urgency=summary.urgency,
    )


@router.post("/drafts", response_model=list[dict])
async def generate_drafts(
    body: AIGenerateDraftsRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Generate AI draft replies for an email.

    Returns draft proposals for user review. NEVER sends automatically.
    """
    email = await _fetch_email_content(db, user_id, body.message_id, settings)
    ai = get_ai_service(settings)

    drafts = await ai.generate_drafts(
        **email,
        user_context=body.user_context,
        num_drafts=body.num_drafts,
    )

    return [d.model_dump() for d in drafts]


@router.post("/extract-event", response_model=EventProposalResponse | None)
async def extract_event(
    body: AIExtractEventRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Extract calendar event from an email using AI."""
    email = await _fetch_email_content(db, user_id, body.message_id, settings)
    ai = get_ai_service(settings)
    event_svc = EventService(ai)

    proposed = await event_svc.extract_and_propose(
        db=db,
        user_id=user_id,
        message_id=body.message_id,
        **email,
    )

    if proposed is None:
        return None

    return EventProposalResponse(
        id=str(proposed.id),
        message_id=proposed.message_id,
        event_data=proposed.event_data,
        status=proposed.status.value,
        created_at=proposed.created_at.isoformat(),
    )
