"""Celery tasks for Gmail processing."""

import logging

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.models.alert import Alert
from app.models.oauth_token import OAuthToken
from app.models.processed_message import ProcessedMessage
from app.models.rule import Rule
from app.models.user import User
from app.models.user_preference import UserPreference
from app.services.crypto_service import get_crypto_service
from app.services.gmail_parser import parse_gmail_message
from app.services.gmail_service import GmailService
from app.services.rules_engine import evaluate_rule

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Create a synchronous DB session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()
    # Convert async URL to sync
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(sync_url)
    return sessionmaker(bind=engine)()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    name="app.tasks.gmail_tasks.process_gmail_notification",
)
def process_gmail_notification(self, email_address: str, history_id: str):
    """Process a Gmail push notification.

    Flow:
    1. Find user by email
    2. Fetch history since last known historyId
    3. For each new message: idempotent insert, match rules, create alerts
    4. Trigger push notifications for matches
    """
    settings = get_settings()
    session = _get_sync_session()

    try:
        # Find user
        user = session.execute(select(User).where(User.email == email_address)).scalar_one_or_none()

        if not user:
            logger.warning("No user found for email (notification ignored)")
            return

        # Get OAuth token
        oauth_token = session.execute(select(OAuthToken).where(OAuthToken.user_id == user.id)).scalar_one_or_none()

        if not oauth_token:
            logger.warning("No OAuth token for user=%s", user.id)
            return

        # Determine start historyId
        start_history = oauth_token.last_history_id or history_id

        # Fetch history (synchronous wrapper)
        crypto = get_crypto_service(settings)
        gmail = GmailService(settings, crypto)

        import asyncio

        loop = asyncio.new_event_loop()
        try:
            history_records = loop.run_until_complete(
                gmail.get_history(
                    encrypted_access_token=oauth_token.encrypted_access_token,
                    encrypted_refresh_token=oauth_token.encrypted_refresh_token,
                    start_history_id=start_history,
                )
            )
        finally:
            loop.close()

        # Get user's active rules
        rules = (
            session.execute(
                select(Rule).where(Rule.user_id == user.id, Rule.is_active == True)  # noqa: E712
            )
            .scalars()
            .all()
        )

        rule_dicts = [{"id": str(r.id), "name": r.name, "conditions": r.conditions} for r in rules]

        # Fetch user preferences for auto-categorize
        user_pref = session.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        ).scalar_one_or_none()

        new_message_ids = set()
        for record in history_records:
            for msg_added in record.get("messagesAdded", []):
                msg_id = msg_added.get("message", {}).get("id")
                if msg_id:
                    new_message_ids.add(msg_id)

        logger.info("Processing %d new messages for user=%s", len(new_message_ids), user.id)

        for msg_id in new_message_ids:
            _process_single_message(
                session=session,
                user=user,
                gmail=gmail,
                oauth_token=oauth_token,
                message_id=msg_id,
                rule_dicts=rule_dicts,
                settings=settings,
                user_pref=user_pref,
            )

        # Update last historyId
        oauth_token.last_history_id = history_id
        session.commit()

        logger.info("Gmail notification processed for user=%s, history=%s", user.id, history_id)

    except Exception as e:
        session.rollback()
        logger.error("Gmail task failed: %s", e)
        raise
    finally:
        session.close()


def _process_single_message(
    session,
    user: User,
    gmail: GmailService,
    oauth_token: OAuthToken,
    message_id: str,
    rule_dicts: list[dict],
    settings,
    user_pref: UserPreference | None = None,
):
    """Process a single Gmail message: insert, match rules, create alerts, auto-categorize."""
    import asyncio

    # Fetch full message
    loop = asyncio.new_event_loop()
    try:
        raw_msg = loop.run_until_complete(
            gmail.get_message(
                encrypted_access_token=oauth_token.encrypted_access_token,
                encrypted_refresh_token=oauth_token.encrypted_refresh_token,
                message_id=message_id,
            )
        )
    finally:
        loop.close()

    parsed = parse_gmail_message(raw_msg)

    # Auto-categorize via AI if enabled
    category = None
    if user_pref and user_pref.auto_categorize_enabled:
        try:
            from app.services.ai_service import get_ai_service

            ai = get_ai_service(settings)
            loop = asyncio.new_event_loop()
            try:
                summary = loop.run_until_complete(
                    ai.summarize(
                        from_addr=parsed.from_addr or "unknown",
                        subject=parsed.subject or "(no subject)",
                        date=str(parsed.received_at or ""),
                        body=parsed.snippet or "",
                    )
                )
                if summary:
                    category = summary.category
            finally:
                loop.close()
        except Exception as e:
            logger.warning("Auto-categorize failed for message %s: %s", message_id, e)

    # Idempotent insert
    stmt = (
        pg_insert(ProcessedMessage)
        .values(
            user_id=user.id,
            message_id=parsed.message_id,
            thread_id=parsed.thread_id,
            subject=parsed.subject,
            from_addr=parsed.from_addr,
            snippet=parsed.snippet,
            has_attachment=parsed.has_attachment,
            label_ids=",".join(parsed.label_ids) if parsed.label_ids else None,
            category=category,
            received_at=parsed.received_at,
        )
        .on_conflict_do_nothing(constraint="uq_user_message")
        .returning(ProcessedMessage.id)
    )

    result = session.execute(stmt)
    inserted = result.fetchone()

    if not inserted:
        # Already processed
        logger.debug("Message %s already processed for user=%s", message_id, user.id)
        return

    session.flush()

    # Auto-label in Gmail if enabled and category was detected
    if user_pref and user_pref.auto_label_enabled and category:
        try:
            label_name = f"EHA/{category}"
            loop = asyncio.new_event_loop()
            try:
                label_id = loop.run_until_complete(
                    gmail.get_or_create_label(
                        encrypted_access_token=oauth_token.encrypted_access_token,
                        encrypted_refresh_token=oauth_token.encrypted_refresh_token,
                        label_name=label_name,
                    )
                )
                loop.run_until_complete(
                    gmail.modify_message_labels(
                        encrypted_access_token=oauth_token.encrypted_access_token,
                        encrypted_refresh_token=oauth_token.encrypted_refresh_token,
                        message_id=parsed.message_id,
                        add_label_ids=[label_id],
                    )
                )
            finally:
                loop.close()
            logger.info("Applied label %s to message %s", label_name, message_id)
        except Exception as e:
            logger.warning("Auto-label failed for message %s: %s", message_id, e)

    # Match against rules
    for rule_dict in rule_dicts:
        if evaluate_rule(rule_dict["conditions"], parsed):
            alert = Alert(
                user_id=user.id,
                message_id=parsed.message_id,
                rule_id=rule_dict["id"],
            )
            session.add(alert)
            session.flush()

            # Trigger push notification async
            from app.tasks.notification_tasks import send_push_for_alert

            send_push_for_alert.delay(
                user_id=str(user.id),
                alert_id=str(alert.id),
                subject=parsed.subject or "(no subject)",
                from_addr=parsed.from_addr or "unknown",
                rule_name=rule_dict["name"],
            )

    session.commit()


@shared_task(name="app.tasks.gmail_tasks.poll_gmail_fallback")
def poll_gmail_fallback():
    """Fallback polling for users whose Pub/Sub watch may have expired.

    Runs on Celery beat schedule. Re-establishes watch and checks for new messages.
    """
    settings = get_settings()
    session = _get_sync_session()

    try:
        # Find all users with OAuth tokens
        tokens = session.execute(select(OAuthToken)).scalars().all()

        for token in tokens:
            try:
                crypto = get_crypto_service(settings)
                gmail = GmailService(settings, crypto)

                import asyncio

                loop = asyncio.new_event_loop()
                try:
                    # Re-establish watch (idempotent)
                    watch_response = loop.run_until_complete(
                        gmail.setup_watch(
                            encrypted_access_token=token.encrypted_access_token,
                            encrypted_refresh_token=token.encrypted_refresh_token,
                        )
                    )
                finally:
                    loop.close()

                new_history_id = str(watch_response.get("historyId", ""))
                if new_history_id and token.last_history_id:
                    # Fetch any missed history
                    user = session.execute(select(User).where(User.id == token.user_id)).scalar_one_or_none()

                    if user:
                        process_gmail_notification.delay(
                            email_address=user.email,
                            history_id=new_history_id,
                        )

            except Exception as e:
                logger.warning("Poll fallback failed for user=%s: %s", token.user_id, e)

    finally:
        session.close()
