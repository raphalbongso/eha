"""Rule schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RuleCondition(BaseModel):
    type: Literal[
        "from_contains",
        "subject_contains",
        "has_attachment",
        "label",
        "body_keywords",
        "time_window",
    ]
    value: Any


class RuleConditions(BaseModel):
    logic: Literal["AND", "OR"] = "AND"
    conditions: list[RuleCondition] = Field(..., min_length=1)


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    conditions: RuleConditions
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    conditions: RuleConditions | None = None
    is_active: bool | None = None


class RuleResponse(BaseModel):
    id: str
    name: str
    conditions: dict[str, Any]
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
