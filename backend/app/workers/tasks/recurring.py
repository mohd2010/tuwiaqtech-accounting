"""Recurring entry processing task — posts entries whose next_run_date is due."""

from __future__ import annotations

from datetime import date

from backend.app.workers.celery_app import celery


@celery.task(name="backend.app.workers.tasks.recurring.process_due_entries")
def process_due_entries() -> dict:
    """Find all ACTIVE recurring entries due today (or earlier) and post them."""
    from backend.app.core.database import SessionLocal
    from backend.app.models.recurring import RecurringEntry, RecurringStatus
    from backend.app.services.recurring import post_recurring_entry

    db = SessionLocal()
    try:
        today = date.today()
        due = (
            db.query(RecurringEntry)
            .filter(
                RecurringEntry.status == RecurringStatus.ACTIVE,
                RecurringEntry.next_run_date <= today,
            )
            .all()
        )
        posted = 0
        errors: list[str] = []
        for entry in due:
            try:
                post_recurring_entry(db, entry_id=entry.id, user_id=entry.created_by)
                db.commit()
                posted += 1
            except Exception as exc:
                db.rollback()
                errors.append(f"{entry.id}: {exc}")

        return {"posted": posted, "errors": errors}
    finally:
        db.close()
