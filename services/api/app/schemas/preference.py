"""User preferences schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class PreferenceResponse(BaseModel):
    home_address: str | None = None
    work_address: str | None = None
    preferred_transport_mode: str | None = "driving"
    auto_categorize_enabled: bool = False
    auto_label_enabled: bool = False
    store_email_content: bool = False

    model_config = {"from_attributes": True}


class PreferenceUpdate(BaseModel):
    home_address: str | None = Field(None, max_length=500)
    work_address: str | None = Field(None, max_length=500)
    preferred_transport_mode: Literal["driving", "transit", "cycling", "walking"] | None = None
    auto_categorize_enabled: bool | None = None
    auto_label_enabled: bool | None = None
    store_email_content: bool | None = None
