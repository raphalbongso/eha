"""Device token registration for push notifications."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_id, get_db
from app.models.device_token import DeviceToken
from app.schemas.notification import DeviceRegisterRequest, DeviceRegisterResponse

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/register", response_model=DeviceRegisterResponse, status_code=201)
async def register_device(
    body: DeviceRegisterRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Register a device for push notifications.

    If the device_id already exists for this user, update the token.
    Supports multiple devices per user.
    """
    # Check if device already registered
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == user_id,
            DeviceToken.device_id == body.device_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.token = body.token
        existing.platform = body.platform
        await db.flush()
        device = existing
    else:
        device = DeviceToken(
            user_id=user_id,
            platform=body.platform,
            token=body.token,
            device_id=body.device_id,
        )
        db.add(device)
        await db.flush()

    return DeviceRegisterResponse(
        id=str(device.id),
        platform=device.platform,
        device_id=device.device_id,
        created_at=device.created_at.isoformat(),
    )
