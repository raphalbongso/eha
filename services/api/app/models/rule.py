"""Rule model for email matching rules."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Rule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Conditions stored as JSONB:
    # {
    #   "logic": "AND" | "OR",
    #   "conditions": [
    #     {"type": "from_contains", "value": "boss@company.com"},
    #     {"type": "subject_contains", "value": "urgent"},
    #     {"type": "has_attachment", "value": true},
    #     {"type": "label", "value": "IMPORTANT"},
    #     {"type": "body_keywords", "value": ["deadline", "asap"]},
    #     {"type": "time_window", "value": {"start": "09:00", "end": "17:00", "timezone": "Europe/Amsterdam"}}
    #   ]
    # }
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="rules")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="rule")

    def __repr__(self) -> str:
        return f"<Rule {self.name} user_id={self.user_id}>"
