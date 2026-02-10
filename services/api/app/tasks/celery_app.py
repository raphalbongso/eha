"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "eha",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        "app.tasks.gmail_tasks.*": {"queue": "gmail"},
        "app.tasks.notification_tasks.*": {"queue": "notifications"},
        "app.tasks.automation_tasks.*": {"queue": "default"},
        "app.tasks.retention_tasks.*": {"queue": "default"},
    },
    beat_schedule={
        # Gmail polling fallback: run every 60s for users whose watch may have expired
        "gmail-poll-fallback": {
            "task": "app.tasks.gmail_tasks.poll_gmail_fallback",
            "schedule": settings.gmail_poll_interval,
        },
        # Cleanup stale device tokens: daily at 3 AM UTC
        "cleanup-stale-tokens": {
            "task": "app.tasks.notification_tasks.cleanup_stale_device_tokens",
            "schedule": crontab(hour=3, minute=0),
        },
        # v2: Check for upcoming events needing leave-time alerts (every 15 min)
        "check-upcoming-events": {
            "task": "app.tasks.leave_time_tasks.check_upcoming_events",
            "schedule": crontab(minute="*/15"),
        },
        # v3: Check follow-up reminders (every 30 min)
        "check-follow-up-reminders": {
            "task": "app.tasks.automation_tasks.check_follow_up_reminders",
            "schedule": crontab(minute="*/30"),
        },
        # v3: Check upcoming meetings for prep summaries (every hour)
        "check-upcoming-meetings": {
            "task": "app.tasks.automation_tasks.check_upcoming_meetings",
            "schedule": crontab(minute=0),
        },
        # v3: Send digest notifications (every hour)
        "send-digest-notifications": {
            "task": "app.tasks.automation_tasks.send_digest_notifications",
            "schedule": crontab(minute=0),
        },
        # v2: Cleanup expired AI data: daily at 4 AM UTC
        "cleanup-expired-ai-data": {
            "task": "app.tasks.retention_tasks.cleanup_expired_ai_data",
            "schedule": crontab(hour=4, minute=0),
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
