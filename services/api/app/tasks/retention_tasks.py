"""Celery tasks for AI data retention cleanup."""

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import delete, select, update

from app.config import get_settings
from app.models.draft import Draft
from app.models.processed_message import ProcessedMessage
from app.models.proposed_event import EventStatus, ProposedEvent
from app.models.user_preference import UserPreference

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Create a synchronous DB session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(sync_url)
    return sessionmaker(bind=engine)()


@shared_task(name="app.tasks.retention_tasks.cleanup_expired_ai_data")
def cleanup_expired_ai_data():
    """Delete or scrub AI-generated data older than each user's retention period."""
    session = _get_sync_session()
    try:
        prefs = session.execute(
            select(UserPreference).where(
                UserPreference.ai_data_retention_days.isnot(None)
            )
        ).scalars().all()

        for pref in prefs:
            cutoff = datetime.now(timezone.utc) - timedelta(days=pref.ai_data_retention_days)
            uid = pref.user_id

            # 1. Delete old drafts
            draft_result = session.execute(
                delete(Draft).where(
                    Draft.user_id == uid,
                    Draft.created_at < cutoff,
                )
            )

            # 2. Delete old non-proposed events (dismissed/confirmed)
            event_result = session.execute(
                delete(ProposedEvent).where(
                    ProposedEvent.user_id == uid,
                    ProposedEvent.created_at < cutoff,
                    ProposedEvent.status != EventStatus.PROPOSED,
                )
            )

            # 3. Scrub AI fields on old processed messages (keep the row)
            msg_result = session.execute(
                update(ProcessedMessage)
                .where(
                    ProcessedMessage.user_id == uid,
                    ProcessedMessage.processed_at < cutoff,
                )
                .where(
                    (ProcessedMessage.category.isnot(None))
                    | (ProcessedMessage.encrypted_body_text.isnot(None))
                    | (ProcessedMessage.encrypted_body_html.isnot(None))
                )
                .values(
                    category=None,
                    encrypted_body_text=None,
                    encrypted_body_html=None,
                )
            )

            logger.info(
                "Retention cleanup for user %s (cutoff=%s): "
                "%d drafts deleted, %d events deleted, %d messages scrubbed",
                uid,
                cutoff.isoformat(),
                draft_result.rowcount,
                event_result.rowcount,
                msg_result.rowcount,
            )

        session.commit()
        logger.info("AI data retention cleanup complete for %d users", len(prefs))
    except Exception as e:
        session.rollback()
        logger.error("AI data retention cleanup failed: %s", e)
        raise
    finally:
        session.close()
