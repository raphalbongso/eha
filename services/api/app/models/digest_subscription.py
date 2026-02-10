"""Digest subscription model for daily/weekly email summaries."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class DigestSubscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "digest_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    frequency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="daily"
    )  # "daily" or "weekly"
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # 0=Mon, for weekly
    hour_utc: Mapped[int] = mapped_column(
        Integer, nullable=False, default=8
    )  # 0-23
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<DigestSubscription {self.id} freq={self.frequency}>"
