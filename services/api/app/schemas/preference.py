"""User preferences schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class PreferenceResponse(BaseModel):
    home_address: str | None = None
    work_address: str | None = None
    preferred_transport_mode: str | None = "driving"

    model_config = {"from_attributes": True}


class PreferenceUpdate(BaseModel):
    home_address: str | None = Field(None, max_length=500)
    work_address: str | None = Field(None, max_length=500)
    preferred_transport_mode: Literal["driving", "transit", "cycling", "walking"] | None = None
