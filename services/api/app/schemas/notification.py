"""Notification and device schemas."""

from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    platform: str = Field(..., pattern="^(ios|android)$")
    token: str = Field(..., min_length=1, max_length=512)
    device_id: str = Field(..., min_length=1, max_length=255)


class DeviceRegisterResponse(BaseModel):
    id: str
    platform: str
    device_id: str
    created_at: str

    model_config = {"from_attributes": True}
