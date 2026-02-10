"""User preferences routes (v2)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_id, get_db
from app.models.user_preference import UserPreference
from app.schemas.preference import PreferenceResponse, PreferenceUpdate

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferenceResponse)
async def get_preferences(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's preferences."""
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    pref = result.scalar_one_or_none()
    if not pref:
        return PreferenceResponse()
    return PreferenceResponse.model_validate(pref)


@router.put("", response_model=PreferenceResponse)
async def update_preferences(
    body: PreferenceUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create or update user preferences."""
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    pref = result.scalar_one_or_none()

    if pref is None:
        pref = UserPreference(user_id=user_id)
        db.add(pref)

    if body.home_address is not None:
        pref.home_address = body.home_address
    if body.work_address is not None:
        pref.work_address = body.work_address
    if body.preferred_transport_mode is not None:
        pref.preferred_transport_mode = body.preferred_transport_mode
    if body.auto_categorize_enabled is not None:
        pref.auto_categorize_enabled = body.auto_categorize_enabled
    if body.auto_label_enabled is not None:
        pref.auto_label_enabled = body.auto_label_enabled
    if body.store_email_content is not None:
        pref.store_email_content = body.store_email_content
    if body.ai_data_retention_days is not None:
        # 0 means "clear retention" (keep forever); any positive value sets the period
        pref.ai_data_retention_days = body.ai_data_retention_days or None

    await db.flush()
    return PreferenceResponse.model_validate(pref)
