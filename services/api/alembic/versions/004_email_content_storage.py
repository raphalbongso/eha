"""Optional email content storage (user opt-in, encrypted).

Revision ID: 004_email_content_storage
Revises: 003_slack_notifications
Create Date: 2025-07-15 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "004_email_content_storage"
down_revision = "003_slack_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "processed_messages",
        sa.Column("encrypted_body_text", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "processed_messages",
        sa.Column("encrypted_body_html", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column(
            "store_email_content",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "store_email_content")
    op.drop_column("processed_messages", "encrypted_body_html")
    op.drop_column("processed_messages", "encrypted_body_text")
