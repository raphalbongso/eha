"""Proposed event model for calendar integration."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class EventStatus(str, enum.Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class ProposedEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "proposed_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # event_data JSONB stores:
    # {
    #   "title": "string",
    #   "start_datetime": "ISO8601",
    #   "end_datetime": "ISO8601 | null",
    #   "duration_minutes": number | null,
    #   "location": "string | null",
    #   "attendees": ["email"] | null,
    #   "confidence": 0.0 - 1.0
    # }
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status"),
        default=EventStatus.PROPOSED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="proposed_events")

    def __repr__(self) -> str:
        return f"<ProposedEvent {self.id} status={self.status}>"
