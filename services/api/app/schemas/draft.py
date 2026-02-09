"""Draft schemas."""

from pydantic import BaseModel, Field


class DraftCreateRequest(BaseModel):
    message_id: str
    to: str
    subject: str
    body: str
    tone: str = Field(..., pattern="^(formal|friendly|brief)$")
    thread_id: str | None = None
    in_reply_to: str | None = None


class DraftResponse(BaseModel):
    id: str
    message_id: str
    gmail_draft_id: str | None
    content_preview: str
    tone: str
    created_at: str

    model_config = {"from_attributes": True}


class AIGenerateDraftsRequest(BaseModel):
    message_id: str
    user_context: str = ""
    num_drafts: int = Field(default=3, ge=1, le=5)


class AISummarizeRequest(BaseModel):
    message_id: str


class SummaryResponse(BaseModel):
    summary: str
    action_items: list[str]
    urgency: str


class AIExtractEventRequest(BaseModel):
    message_id: str
