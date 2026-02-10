"""Follow-up reminder model for tracking unanswered sent emails."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class ReminderStatus(str, enum.Enum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    DISMISSED = "dismissed"


class FollowUpReminder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "follow_up_reminders"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    remind_after_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, name="reminder_status"),
        default=ReminderStatus.PENDING,
        nullable=False,
    )
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<FollowUpReminder {self.id} status={self.status.value}>"
