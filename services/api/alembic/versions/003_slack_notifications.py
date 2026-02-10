"""Slack notification configs.

Revision ID: 003_slack_notifications
Revises: 002_smart_automation
Create Date: 2025-07-01 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003_slack_notifications"
down_revision = "002_smart_automation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slack_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("webhook_url", sa.LargeBinary(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "enabled_notification_types",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_slack_configs_user_id", "slack_configs", ["user_id"])


def downgrade() -> None:
    op.drop_table("slack_configs")
