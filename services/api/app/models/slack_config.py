"""Slack notification configuration model."""

import uuid

from sqlalchemy import Boolean, ForeignKey, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SlackConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-user Slack webhook configuration for notifications."""

    __tablename__ = "slack_configs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    webhook_url: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="Encrypted Slack incoming webhook URL",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    enabled_notification_types: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="'[]'::jsonb",
        comment="List of NotificationType strings; empty = all types enabled",
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<SlackConfig user_id={self.user_id} enabled={self.is_enabled}>"
