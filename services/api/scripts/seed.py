"""Seed script: populates dev DB with sample user, rules, and alerts."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.alert import Alert
from app.models.base import Base
from app.models.rule import Rule
from app.models.user import User

SEED_USER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
SEED_GOOGLE_ID = "seed_google_id_12345"
SEED_EMAIL = "dev@example.com"


async def seed():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        # Check if seed user already exists
        result = await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": SEED_EMAIL})
        if result.scalar():
            print(f"Seed user {SEED_EMAIL} already exists — skipping.")
            await engine.dispose()
            return

        now = datetime.now(timezone.utc)

        # Create user
        user = User(id=SEED_USER_ID, google_id=SEED_GOOGLE_ID, email=SEED_EMAIL, name="Dev User")
        db.add(user)
        await db.flush()

        # Create sample rules
        rule_boss = Rule(
            user_id=SEED_USER_ID,
            name="Boss emails",
            conditions={
                "logic": "AND",
                "conditions": [{"type": "from_contains", "value": "boss@company.com"}],
            },
            is_active=True,
        )
        rule_urgent = Rule(
            user_id=SEED_USER_ID,
            name="Urgent subject",
            conditions={
                "logic": "OR",
                "conditions": [
                    {"type": "subject_contains", "value": "urgent"},
                    {"type": "body_keywords", "value": ["ASAP", "deadline", "critical"]},
                ],
            },
            is_active=True,
        )
        rule_attachments = Rule(
            user_id=SEED_USER_ID,
            name="Has attachment",
            conditions={
                "logic": "AND",
                "conditions": [{"type": "has_attachment", "value": True}],
            },
            is_active=True,
        )
        db.add_all([rule_boss, rule_urgent, rule_attachments])
        await db.flush()

        # Create sample alerts
        for i, rule in enumerate([rule_boss, rule_urgent, rule_attachments]):
            alert = Alert(
                user_id=SEED_USER_ID,
                message_id=f"seed_msg_{i + 1:03d}",
                rule_id=rule.id,
                read=i == 0,
            )
            db.add(alert)

        await db.commit()
        print(f"Seeded: user={SEED_EMAIL}, 3 rules, 3 alerts")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
