"""Slack notification configuration endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_current_user_id, get_db
from app.models.slack_config import SlackConfig
from app.schemas.slack import SlackConfigResponse, SlackConfigUpdate, SlackTestResponse
from app.services.crypto_service import get_crypto_service
from app.services.push_service import NotificationType
from app.services.slack_service import get_slack_service

router = APIRouter(prefix="/slack", tags=["slack"])


def _mask_webhook(url: str) -> str:
    """Mask webhook URL, showing only last 6 chars."""
    if len(url) <= 10:
        return "****"
    return f"****{url[-6:]}"


@router.get("/config", response_model=SlackConfigResponse)
async def get_slack_config(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Get the current user's Slack notification config."""
    result = await db.execute(
        select(SlackConfig).where(SlackConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Slack config found")

    crypto = get_crypto_service(settings)
    webhook_url = crypto.decrypt(config.webhook_url)

    return SlackConfigResponse(
        webhook_url_masked=_mask_webhook(webhook_url),
        is_enabled=config.is_enabled,
        enabled_notification_types=config.enabled_notification_types or [],
        created_at=config.created_at,
    )


@router.put("/config", response_model=SlackConfigResponse, status_code=200)
async def update_slack_config(
    body: SlackConfigUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Create or update the user's Slack notification config."""
    crypto = get_crypto_service(settings)

    result = await db.execute(
        select(SlackConfig).where(SlackConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if config:
        # Update existing
        if body.webhook_url is not None:
            config.webhook_url = crypto.encrypt(body.webhook_url)
        config.is_enabled = body.is_enabled
        config.enabled_notification_types = body.enabled_notification_types
    else:
        # Create new — webhook_url required
        if body.webhook_url is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="webhook_url is required when creating a new config",
            )
        config = SlackConfig(
            user_id=user_id,
            webhook_url=crypto.encrypt(body.webhook_url),
            is_enabled=body.is_enabled,
            enabled_notification_types=body.enabled_notification_types,
        )
        db.add(config)

    await db.flush()

    webhook_url = crypto.decrypt(config.webhook_url)
    return SlackConfigResponse(
        webhook_url_masked=_mask_webhook(webhook_url),
        is_enabled=config.is_enabled,
        enabled_notification_types=config.enabled_notification_types or [],
        created_at=config.created_at,
    )


@router.post("/test", response_model=SlackTestResponse)
async def test_slack_notification(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Send a test notification to the user's configured Slack webhook."""
    result = await db.execute(
        select(SlackConfig).where(SlackConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Slack config found")

    crypto = get_crypto_service(settings)
    webhook_url = crypto.decrypt(config.webhook_url)

    slack = get_slack_service()
    success = await slack.send(
        webhook_url=webhook_url,
        title="EHA Test Notification",
        body="If you see this, your Slack integration is working!",
        notification_type=NotificationType.SYSTEM,
    )

    if success:
        return SlackTestResponse(success=True, message="Test notification sent successfully")
    else:
        return SlackTestResponse(success=False, message="Failed to send test notification. Check your webhook URL.")


@router.delete("/config", status_code=204)
async def delete_slack_config(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove the user's Slack notification config."""
    result = await db.execute(
        select(SlackConfig).where(SlackConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Slack config found")

    await db.delete(config)
    await db.flush()
