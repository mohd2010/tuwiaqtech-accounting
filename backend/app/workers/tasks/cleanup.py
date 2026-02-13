"""Periodic cleanup tasks."""

from __future__ import annotations

from backend.app.workers.celery_app import celery


@celery.task(name="backend.app.workers.tasks.cleanup.cleanup_revoked_tokens")
def cleanup_revoked_tokens() -> dict:
    """Purge expired entries from the in-memory revoked-token set.

    The JWT expiry time is checked — tokens past their ``exp`` claim are
    removed since they can no longer be used.
    """
    from backend.app.core.security import cleanup_expired_tokens

    removed = cleanup_expired_tokens()
    return {"removed": removed}
