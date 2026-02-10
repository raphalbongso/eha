"""Request/response schemas for smart automation endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# --- Follow-up reminders ---

class FollowUpReminderCreate(BaseModel):
    message_id: str = Field(..., max_length=255)
    thread_id: str = Field(..., max_length=255)
    remind_after_hours: int = Field(72, ge=1, le=720)


class FollowUpReminderResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    message_id: str
    thread_id: str
    remind_after_hours: int
    status: str
    triggered_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FollowUpReminderList(BaseModel):
    reminders: list[FollowUpReminderResponse]
    total: int


# --- Meeting prep ---

class MeetingPrepResponse(BaseModel):
    event_id: str
    agenda_context: str
    key_discussion_points: list[str]
    open_action_items: list[str]
    relevant_attachments: list[str]


# --- Digest subscriptions ---

class DigestSubscriptionCreate(BaseModel):
    frequency: str = Field("daily", pattern="^(daily|weekly)$")
    day_of_week: int = Field(0, ge=0, le=6)
    hour_utc: int = Field(8, ge=0, le=23)


class DigestSubscriptionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    frequency: str
    day_of_week: int
    hour_utc: int
    is_active: bool
    last_sent_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DigestSubscriptionUpdate(BaseModel):
    frequency: str | None = Field(None, pattern="^(daily|weekly)$")
    day_of_week: int | None = Field(None, ge=0, le=6)
    hour_utc: int | None = Field(None, ge=0, le=23)


class DigestPreviewResponse(BaseModel):
    summary: str
    alert_count: int
    highlights: list[str]
    period_start: datetime
    period_end: datetime
