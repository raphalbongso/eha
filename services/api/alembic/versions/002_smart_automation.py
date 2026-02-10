"""v3 Smart Automation: auto-categorize, follow-up reminders, meeting prep, digest.

Revision ID: 002_smart_automation
Revises: 001_initial
Create Date: 2025-06-01 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002_smart_automation"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Add category column to processed_messages ---
    op.add_column(
        "processed_messages",
        sa.Column("category", sa.String(50), nullable=True),
    )

    # --- Add auto-categorize/label preferences to user_preferences ---
    op.add_column(
        "user_preferences",
        sa.Column("auto_categorize_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "user_preferences",
        sa.Column("auto_label_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # --- Create follow_up_reminders table ---
    op.create_table(
        "follow_up_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("remind_after_hours", sa.Integer(), nullable=False, server_default="72"),
        sa.Column(
            "status",
            sa.Enum("pending", "triggered", "dismissed", name="reminder_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_follow_up_reminders_user_id", "follow_up_reminders", ["user_id"])
    op.create_index("ix_follow_up_reminders_status", "follow_up_reminders", ["status"])

    # --- Create digest_subscriptions table ---
    op.create_table(
        "digest_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("frequency", sa.String(10), nullable=False, server_default="daily"),
        sa.Column("day_of_week", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hour_utc", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_digest_subscriptions_user_id", "digest_subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_table("digest_subscriptions")
    op.execute("DROP TYPE IF EXISTS reminder_status")
    op.drop_table("follow_up_reminders")
    op.drop_column("user_preferences", "auto_label_enabled")
    op.drop_column("user_preferences", "auto_categorize_enabled")
    op.drop_column("processed_messages", "category")
