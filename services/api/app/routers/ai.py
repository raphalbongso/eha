"""AI routes: summarize, generate drafts, extract events, categorize, threads, smart drafts, priority inbox."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_current_user_id, get_db
from app.models.oauth_token import OAuthToken
from app.models.processed_message import ProcessedMessage
from app.schemas.draft import (
    AICategorizeBatchRequest,
    AICategorizeBatchResponse,
    AIExtractEventRequest,
    AIGenerateDraftsRequest,
    AISmartDraftsRequest,
    AISummarizeRequest,
    AIThreadDraftsRequest,
    AIThreadSummarizeRequest,
    CategorizeBatchItem,
    PriorityInboxItem,
    PriorityInboxRequest,
    PriorityInboxResponse,
    StyleDraftResponse,
    SummaryResponse,
    ThreadSummaryResponse,
)
from app.schemas.event import EventProposalResponse
from app.services.ai_service import get_ai_service
from app.services.crypto_service import get_crypto_service
from app.services.event_service import EventService
from app.services.gmail_parser import parse_gmail_message
from app.services.gmail_service import get_gmail_service
from app.services.priority_service import compute_heuristic_priority

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
        category=summary.category,
        priority_score=summary.priority_score,
        priority_signals=summary.priority_signals,
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


async def _get_oauth_token(db: AsyncSession, user_id: uuid.UUID) -> OAuthToken:
    """Get OAuth token for a user or raise 400."""
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    return token


async def _fetch_thread_content(
    db: AsyncSession,
    user_id: uuid.UUID,
    thread_id: str,
    settings: Settings,
) -> list[dict]:
    """Fetch all messages in a Gmail thread, parsed for AI processing."""
    token = await _get_oauth_token(db, user_id)
    crypto = get_crypto_service(settings)
    gmail = get_gmail_service(settings, crypto)

    raw_thread = await gmail.get_thread(
        encrypted_access_token=token.encrypted_access_token,
        encrypted_refresh_token=token.encrypted_refresh_token,
        thread_id=thread_id,
    )

    messages = []
    for raw_msg in raw_thread.get("messages", []):
        parsed = parse_gmail_message(raw_msg)
        messages.append({
            "from_addr": parsed.from_addr or "unknown",
            "subject": parsed.subject or "(no subject)",
            "date": parsed.received_at.isoformat() if parsed.received_at else "unknown",
            "body": parsed.body_text or parsed.snippet or "",
        })

    return messages


@router.post("/categorize-batch", response_model=AICategorizeBatchResponse)
async def categorize_batch(
    body: AICategorizeBatchRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Batch categorize up to 10 messages concurrently."""
    ai = get_ai_service(settings)

    async def _process_one(message_id: str) -> CategorizeBatchItem:
        try:
            email = await _fetch_email_content(db, user_id, message_id, settings)
            summary = await ai.summarize(**email)
            if summary is None:
                return CategorizeBatchItem(
                    message_id=message_id,
                    category="general",
                    priority_score=0,
                    priority_signals=[],
                    summary="",
                    urgency="low",
                    error="AI summarization failed",
                )
            return CategorizeBatchItem(
                message_id=message_id,
                category=summary.category,
                priority_score=summary.priority_score,
                priority_signals=summary.priority_signals,
                summary=summary.summary,
                urgency=summary.urgency,
            )
        except Exception as e:
            return CategorizeBatchItem(
                message_id=message_id,
                category="general",
                priority_score=0,
                priority_signals=[],
                summary="",
                urgency="low",
                error=str(e),
            )

    results = await asyncio.gather(*[_process_one(mid) for mid in body.message_ids])
    return AICategorizeBatchResponse(results=list(results))


@router.post("/thread/summarize", response_model=ThreadSummaryResponse)
async def summarize_thread(
    body: AIThreadSummarizeRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Summarize an entire email thread."""
    messages = await _fetch_thread_content(db, user_id, body.thread_id, settings)
    if not messages:
        raise HTTPException(status_code=404, detail="Thread not found or empty")

    ai = get_ai_service(settings)
    result = await ai.summarize_thread(messages)
    if result is None:
        raise HTTPException(status_code=500, detail="AI thread summarization failed")

    return ThreadSummaryResponse(
        thread_summary=result.thread_summary,
        message_count=result.message_count,
        participants=result.participants,
        key_decisions=result.key_decisions,
        action_items=result.action_items,
        current_status=result.current_status,
        urgency=result.urgency,
    )


@router.post("/thread/drafts", response_model=list[dict])
async def generate_thread_drafts(
    body: AIThreadDraftsRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Generate reply drafts with full thread context."""
    messages = await _fetch_thread_content(db, user_id, body.thread_id, settings)
    if not messages:
        raise HTTPException(status_code=404, detail="Thread not found or empty")

    ai = get_ai_service(settings)
    drafts = await ai.generate_thread_drafts(
        thread_messages=messages,
        user_context=body.user_context,
        num_drafts=body.num_drafts,
    )
    return [d.model_dump() for d in drafts]


@router.post("/smart-drafts", response_model=StyleDraftResponse)
async def generate_smart_drafts(
    body: AISmartDraftsRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Generate style-aware reply drafts using the user's writing style."""
    email = await _fetch_email_content(db, user_id, body.message_id, settings)

    # Fetch sent samples for style detection
    token = await _get_oauth_token(db, user_id)
    crypto = get_crypto_service(settings)
    gmail = get_gmail_service(settings, crypto)

    raw_sent = await gmail.list_sent_messages(
        encrypted_access_token=token.encrypted_access_token,
        encrypted_refresh_token=token.encrypted_refresh_token,
        max_results=5,
    )

    sent_samples = []
    for raw_msg in raw_sent:
        parsed = parse_gmail_message(raw_msg)
        sent_samples.append({
            "to_addr": ", ".join(parsed.to_addrs) if parsed.to_addrs else "unknown",
            "subject": parsed.subject or "(no subject)",
            "body": parsed.body_text or parsed.snippet or "",
        })

    ai = get_ai_service(settings)
    result = await ai.generate_style_aware_drafts(
        from_addr=email["from_addr"],
        subject=email["subject"],
        date=email["date"],
        body=email["body"],
        sent_samples=sent_samples,
        user_context=body.user_context,
        num_drafts=body.num_drafts,
    )

    if result is None:
        raise HTTPException(status_code=500, detail="AI style-aware draft generation failed")

    return StyleDraftResponse(
        detected_style=result.detected_style.model_dump(),
        drafts=[d.model_dump() for d in result.drafts],
    )


@router.post("/priority-inbox", response_model=PriorityInboxResponse)
async def priority_inbox(
    body: PriorityInboxRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get priority-scored inbox messages (heuristic, no AI calls)."""
    result = await db.execute(
        select(ProcessedMessage)
        .where(ProcessedMessage.user_id == user_id)
        .order_by(ProcessedMessage.received_at.desc())
        .limit(body.limit)
    )
    messages = result.scalars().all()

    scored = []
    for msg in messages:
        priority = compute_heuristic_priority(msg)
        scored.append(PriorityInboxItem(
            message_id=msg.message_id,
            subject=msg.subject,
            from_addr=msg.from_addr,
            snippet=msg.snippet,
            score=priority["score"],
            signals=priority["signals"],
            received_at=msg.received_at.isoformat() if msg.received_at else None,
        ))

    # Sort by score descending
    scored.sort(key=lambda x: x.score, reverse=True)

    return PriorityInboxResponse(messages=scored)
