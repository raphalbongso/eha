"""Add AI data retention preference.

Revision ID: 005_ai_data_retention
Revises: 004_email_content_storage
Create Date: 2025-07-20 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "005_ai_data_retention"
down_revision = "004_email_content_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("ai_data_retention_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "ai_data_retention_days")
