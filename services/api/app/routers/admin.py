"""Admin routes: data deletion, account management."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_current_user_id, get_db
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.device_token import DeviceToken
from app.models.draft import Draft
from app.models.oauth_token import OAuthToken
from app.models.processed_message import ProcessedMessage
from app.models.proposed_event import ProposedEvent
from app.models.rule import Rule
from app.models.user import User
from app.services.audit_service import write_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["admin"])


@router.delete("/me/data", status_code=200)
async def delete_user_data(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Delete all user data. Cascade deletes everything and revokes Google tokens.

    This is the GDPR/privacy-compliant data deletion endpoint.
    """
    # First, audit the deletion request itself
    await write_audit_log(
        db=db,
        user_id=user_id,
        action="user.data_deletion_requested",
        entity_type="user",
        entity_id=str(user_id),
    )

    # Revoke Google tokens if possible
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        try:
            from app.services.crypto_service import get_crypto_service

            crypto = get_crypto_service(settings)
            access_token = crypto.decrypt(oauth_token.encrypted_access_token)

            import httpx

            async with httpx.AsyncClient() as client:
                await client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": access_token},
                )
            logger.info("Google tokens revoked for user=%s", user_id)
        except Exception as e:
            logger.warning("Failed to revoke Google tokens: %s", e)

    # Delete all user data (cascade via FK on User handles most)
    # But explicit for safety:
    for model in [Alert, Draft, ProposedEvent, ProcessedMessage, DeviceToken, Rule, AuditLog, OAuthToken]:
        await db.execute(delete(model).where(model.user_id == user_id))

    # Finally delete the user
    await db.execute(delete(User).where(User.id == user_id))

    logger.info("All data deleted for user=%s", user_id)
    return {"status": "ok", "detail": "All user data deleted"}


@router.get("/me/export")
async def export_user_data(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Export all user data — v2 stub."""
    raise HTTPException(
        status_code=501,
        detail="Data export is planned for v2. Contact support for manual export.",
    )
