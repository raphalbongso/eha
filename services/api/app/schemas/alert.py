"""Alert schemas."""

from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: str
    message_id: str
    rule_id: str | None
    rule_name: str | None = None
    read: bool
    created_at: str
    # Denormalized message info
    subject: str | None = None
    from_addr: str | None = None
    snippet: str | None = None

    model_config = {"from_attributes": True}


class AlertMarkReadRequest(BaseModel):
    alert_ids: list[str]
