"""Admin routes: data deletion, account management, data export."""

import enum
import io
import json
import logging
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_current_user_id, get_db
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.device_token import DeviceToken
from app.models.digest_subscription import DigestSubscription
from app.models.draft import Draft
from app.models.follow_up_reminder import FollowUpReminder
from app.models.oauth_token import OAuthToken
from app.models.processed_message import ProcessedMessage
from app.models.proposed_event import ProposedEvent
from app.models.rule import Rule
from app.models.slack_config import SlackConfig
from app.models.user import User
from app.models.user_preference import UserPreference
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


def _serialize_row(obj: object) -> dict:
    """Convert a SQLAlchemy model instance to a JSON-safe dict.

    Handles UUIDs, datetimes, enums, JSONB, and skips encrypted binary columns.
    """
    result = {}
    mapper = type(obj).__mapper__  # type: ignore[attr-defined]
    for col in mapper.columns:
        key = col.key
        value = getattr(obj, key)
        if isinstance(value, bytes):
            # Skip encrypted binary columns (oauth tokens, webhook URLs)
            continue
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, date):
            value = value.isoformat()
        elif isinstance(value, enum.Enum):
            value = value.value
        result[key] = value
    return result


async def _query_rows(db: AsyncSession, model: type, user_id: uuid.UUID) -> list[dict]:
    """Query all rows for a model filtered by user_id and serialize them."""
    result = await db.execute(select(model).where(model.user_id == user_id))
    return [_serialize_row(row) for row in result.scalars().all()]


@router.get("/me/export")
async def export_user_data(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Export all user data as a downloadable JSON file (GDPR Article 20)."""
    # Fetch user profile
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build export payload
    export_data = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "user": _serialize_row(user),
        "rules": await _query_rows(db, Rule, user_id),
        "alerts": await _query_rows(db, Alert, user_id),
        "drafts": await _query_rows(db, Draft, user_id),
        "processed_messages": await _query_rows(db, ProcessedMessage, user_id),
        "proposed_events": await _query_rows(db, ProposedEvent, user_id),
        "user_preferences": await _query_rows(db, UserPreference, user_id),
        "follow_up_reminders": await _query_rows(db, FollowUpReminder, user_id),
        "digest_subscriptions": await _query_rows(db, DigestSubscription, user_id),
        "slack_configs": await _query_rows(db, SlackConfig, user_id),
        "audit_log": await _query_rows(db, AuditLog, user_id),
    }

    # Audit-log the export
    await write_audit_log(
        db=db,
        user_id=user_id,
        action="user.data_exported",
        entity_type="user",
        entity_id=str(user_id),
    )

    # Serialize and return as downloadable JSON
    json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")
    today = date.today().isoformat()
    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="eha-data-export-{today}.json"',
        },
    )
