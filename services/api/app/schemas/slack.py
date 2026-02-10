"""Slack notification configuration schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SlackConfigResponse(BaseModel):
    webhook_url_masked: str
    is_enabled: bool
    enabled_notification_types: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class SlackConfigUpdate(BaseModel):
    webhook_url: str | None = Field(
        None,
        min_length=1,
        max_length=500,
        description="Slack incoming webhook URL",
    )
    is_enabled: bool = True
    enabled_notification_types: list[str] = Field(
        default_factory=list,
        description="Notification types to send to Slack; empty = all",
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("https://hooks.slack.com/"):
            raise ValueError("Must be a valid Slack webhook URL (https://hooks.slack.com/...)")
        return v

    @field_validator("enabled_notification_types")
    @classmethod
    def validate_notification_types(cls, v: list[str]) -> list[str]:
        valid = {"RULE_MATCH", "FOLLOW_UP", "DIGEST", "MEETING_PREP", "EVENT_PROPOSAL", "SYSTEM"}
        for t in v:
            if t not in valid:
                raise ValueError(f"Invalid notification type: {t}. Valid: {', '.join(sorted(valid))}")
        return v


class SlackTestResponse(BaseModel):
    success: bool
    message: str
