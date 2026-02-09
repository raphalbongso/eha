"""Draft creation service."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draft import Draft
from app.models.oauth_token import OAuthToken
from app.services.audit_service import write_audit_log
from app.services.gmail_service import GmailService

logger = logging.getLogger(__name__)


class DraftService:
    """Service for creating email drafts (NEVER sends automatically)."""

    def __init__(self, gmail_service: GmailService) -> None:
        self._gmail = gmail_service

    async def create_draft(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        message_id: str,
        to: str,
        subject: str,
        body: str,
        tone: str,
        thread_id: str | None = None,
        in_reply_to: str | None = None,
    ) -> Draft:
        """Create a Gmail draft and store a record in the database.

        The draft is created in Gmail's draft folder. The user must
        explicitly open and send it. EHA NEVER sends emails automatically.
        """
        # Get user's OAuth tokens
        result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))
        token = result.scalar_one_or_none()
        if not token:
            raise ValueError("No OAuth token found for user")

        # Create draft in Gmail
        gmail_draft = await self._gmail.create_draft(
            encrypted_access_token=token.encrypted_access_token,
            encrypted_refresh_token=token.encrypted_refresh_token,
            to=to,
            subject=subject,
            body=body,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
        )

        gmail_draft_id = gmail_draft.get("id")

        # Store draft record
        draft = Draft(
            user_id=user_id,
            message_id=message_id,
            gmail_draft_id=gmail_draft_id,
            content_preview=body[:500],
            tone=tone,
        )
        db.add(draft)
        await db.flush()

        # Audit log
        await write_audit_log(
            db=db,
            user_id=user_id,
            action="draft.created",
            entity_type="draft",
            entity_id=str(draft.id),
            metadata={"tone": tone, "gmail_draft_id": gmail_draft_id},
        )

        logger.info("Draft created for user=%s message=%s tone=%s", user_id, message_id, tone)
        return draft
