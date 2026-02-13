"""Async notification tasks."""

from __future__ import annotations

from backend.app.workers.celery_app import celery


@celery.task(name="backend.app.workers.tasks.notifications.send_notification")
def send_notification(
    notification_type: str,
    recipient_email: str,
    template_kwargs: dict,
) -> dict:
    """Send a notification email asynchronously."""
    from backend.app.services.notification_service import (
        NotificationService,
        NotificationType,
    )

    svc = NotificationService()
    try:
        ntype = NotificationType(notification_type)
    except ValueError:
        return {"status": "error", "detail": f"Unknown type: {notification_type}"}

    ok = svc.send(ntype, recipient_email, **template_kwargs)
    return {"status": "sent" if ok else "skipped"}
