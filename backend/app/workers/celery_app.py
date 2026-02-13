"""Celery application instance.

Start the worker::

    celery -A backend.app.workers.celery_app worker --loglevel=info
    celery -A backend.app.workers.celery_app beat --loglevel=info
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from backend.app.core.config import settings

celery = Celery(
    "tuwaiq",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Riyadh",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks in workers/tasks/*.py
celery.autodiscover_tasks(["backend.app.workers.tasks"])

# Beat schedule — periodic tasks
celery.conf.beat_schedule = {
    "process-recurring-entries-daily": {
        "task": "backend.app.workers.tasks.recurring.process_due_entries",
        "schedule": crontab(hour=2, minute=0),  # 2:00 AM Riyadh time
    },
    "cleanup-revoked-tokens-hourly": {
        "task": "backend.app.workers.tasks.cleanup.cleanup_revoked_tokens",
        "schedule": crontab(minute=0),  # Every hour
    },
}
