"""Draft model for AI-generated email drafts."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Draft(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "drafts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    gmail_draft_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_preview: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "formal", "friendly", "brief"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="drafts")

    def __repr__(self) -> str:
        return f"<Draft {self.id} tone={self.tone}>"
