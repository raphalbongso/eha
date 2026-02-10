"""User preferences model for v2 travel/notification settings."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserPreference(Base, TimestampMixin):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    home_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_transport_mode: Mapped[str] = mapped_column(
        String(20), nullable=True, server_default="driving"
    )
    # v3: Smart automation preferences
    auto_categorize_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    auto_label_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="preferences")

    def __repr__(self) -> str:
        return f"<UserPreference user_id={self.user_id}>"
