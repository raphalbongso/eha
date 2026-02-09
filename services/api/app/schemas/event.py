"""Event schemas."""

from typing import Any

from pydantic import BaseModel


class EventProposalResponse(BaseModel):
    id: str
    message_id: str
    event_data: dict[str, Any]
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class EventConfirmRequest(BaseModel):
    event_id: str


class EventDismissRequest(BaseModel):
    event_id: str
