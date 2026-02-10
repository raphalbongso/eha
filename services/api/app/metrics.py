"""Prometheus metric definitions for EHA.

Single source of truth for all custom metrics. Import from here in API and Celery code.
"""

from prometheus_client import Counter, Histogram

# --- Celery task metrics ---

celery_task_total = Counter(
    "eha_celery_task_total",
    "Total Celery tasks executed",
    ["task_name", "status"],
)

celery_task_duration_seconds = Histogram(
    "eha_celery_task_duration_seconds",
    "Celery task execution duration in seconds",
    ["task_name"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

# --- Business metrics ---

emails_processed_total = Counter(
    "eha_emails_processed_total",
    "Total emails processed by Gmail tasks",
)

drafts_created_total = Counter(
    "eha_drafts_created_total",
    "Total drafts created via API",
)

events_proposed_total = Counter(
    "eha_events_proposed_total",
    "Total event proposals by action",
    ["action"],
)

alerts_created_total = Counter(
    "eha_alerts_created_total",
    "Total alerts created from rule matches",
)

notifications_sent_total = Counter(
    "eha_notifications_sent_total",
    "Total notifications sent by type",
    ["type"],
)
