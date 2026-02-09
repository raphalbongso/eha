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
    category: str = "general"
    priority_score: int = 50
    priority_signals: list[str] = []


class AIExtractEventRequest(BaseModel):
    message_id: str


# --- Batch categorization ---


class AICategorizeBatchRequest(BaseModel):
    message_ids: list[str] = Field(..., min_length=1, max_length=10)


class CategorizeBatchItem(BaseModel):
    message_id: str
    category: str
    priority_score: int
    priority_signals: list[str]
    summary: str
    urgency: str
    error: str | None = None


class AICategorizeBatchResponse(BaseModel):
    results: list[CategorizeBatchItem]


# --- Thread context ---


class AIThreadSummarizeRequest(BaseModel):
    thread_id: str


class ThreadSummaryResponse(BaseModel):
    thread_summary: str
    message_count: int
    participants: list[str]
    key_decisions: list[str]
    action_items: list[str]
    current_status: str
    urgency: str


class AIThreadDraftsRequest(BaseModel):
    thread_id: str
    user_context: str = ""
    num_drafts: int = Field(default=3, ge=1, le=5)


# --- Smart (style-aware) drafts ---


class AISmartDraftsRequest(BaseModel):
    message_id: str
    user_context: str = ""
    num_drafts: int = Field(default=3, ge=1, le=5)


class DetectedStyleResponse(BaseModel):
    formality: str
    avg_length: str
    greeting_style: str
    sign_off_style: str
    traits: list[str]


class StyleDraftResponse(BaseModel):
    detected_style: DetectedStyleResponse
    drafts: list[dict]


# --- Priority inbox ---


class PriorityInboxRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=50)


class PriorityInboxItem(BaseModel):
    message_id: str
    subject: str | None
    from_addr: str | None
    snippet: str | None
    score: int
    signals: list[str]
    received_at: str | None


class PriorityInboxResponse(BaseModel):
    messages: list[PriorityInboxItem]
