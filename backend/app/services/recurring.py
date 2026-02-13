"""Service layer for recurring journal entry templates."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.accounting import Account
from backend.app.models.recurring import (
    RecurringEntry,
    RecurringEntrySplit,
    RecurringFrequency,
    RecurringStatus,
)
from backend.app.schemas.accounting import JournalEntryCreate, SplitType, TransactionSplitCreate
from backend.app.services.audit import log_action
from backend.app.services.journal import create_journal_entry


# ─── Date helpers ─────────────────────────────────────────────────────────────


def _add_months(d: date, months: int) -> date:
    """Add *months* calendar months to *d*, clamping to end-of-month."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def _advance_date(current: date, frequency: RecurringFrequency) -> date:
    """Return the next run date after *current* based on *frequency*."""
    if frequency == RecurringFrequency.DAILY:
        return current + timedelta(days=1)
    if frequency == RecurringFrequency.WEEKLY:
        return current + timedelta(weeks=1)
    if frequency == RecurringFrequency.MONTHLY:
        return _add_months(current, 1)
    if frequency == RecurringFrequency.QUARTERLY:
        return _add_months(current, 3)
    # ANNUALLY
    return _add_months(current, 12)


# ─── CRUD ─────────────────────────────────────────────────────────────────────


def list_recurring_entries(db: Session) -> list[dict]:
    """Return all recurring entries, newest-due first, with is_due flag."""
    entries = (
        db.query(RecurringEntry)
        .order_by(RecurringEntry.next_run_date.asc())
        .all()
    )
    today = date.today()
    result: list[dict] = []
    for e in entries:
        is_due = (
            e.status == RecurringStatus.ACTIVE
            and e.next_run_date <= today
            and (e.end_date is None or e.next_run_date <= e.end_date)
        )
        result.append({
            "id": str(e.id),
            "name": e.name,
            "description": e.description,
            "frequency": e.frequency.value,
            "next_run_date": e.next_run_date.isoformat(),
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "status": e.status.value,
            "total_posted": e.total_posted,
            "is_due": is_due,
            "split_count": len(e.splits),
        })
    return result


def get_recurring_entry(db: Session, entry_id: UUID) -> dict:
    """Return a single recurring entry with full split details."""
    entry = db.query(RecurringEntry).filter(RecurringEntry.id == entry_id).first()
    if entry is None:
        raise ValueError("Recurring entry not found")

    splits = []
    for s in entry.splits:
        acct = db.query(Account).filter(Account.id == s.account_id).first()
        splits.append({
            "id": str(s.id),
            "account_id": str(s.account_id),
            "account_code": acct.code if acct else "",
            "account_name": acct.name if acct else "",
            "debit_amount": str(s.debit_amount),
            "credit_amount": str(s.credit_amount),
        })

    return {
        "id": str(entry.id),
        "name": entry.name,
        "description": entry.description,
        "reference_prefix": entry.reference_prefix,
        "frequency": entry.frequency.value,
        "next_run_date": entry.next_run_date.isoformat(),
        "end_date": entry.end_date.isoformat() if entry.end_date else None,
        "status": entry.status.value,
        "last_posted_at": entry.last_posted_at.isoformat() if entry.last_posted_at else None,
        "total_posted": entry.total_posted,
        "created_by": str(entry.created_by),
        "created_at": entry.created_at.isoformat() if entry.created_at else "",
        "splits": splits,
    }


def create_recurring_entry(
    db: Session,
    *,
    name: str,
    description: str,
    reference_prefix: str | None,
    frequency: str,
    next_run_date: date,
    end_date: date | None,
    splits: list[dict],
    user_id: UUID,
) -> RecurringEntry:
    """Create a new recurring entry template.

    *splits* is a list of dicts with keys: account_id, amount, type (DEBIT/CREDIT).
    Does NOT call db.commit() — caller is responsible.
    """
    # Validate frequency
    try:
        freq = RecurringFrequency(frequency)
    except ValueError:
        raise ValueError(f"Invalid frequency: {frequency}")

    # Validate double entry
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for s in splits:
        amt = Decimal(str(s["amount"]))
        if amt <= 0:
            raise ValueError("Split amount must be greater than zero")
        if s["type"].lower() == "debit":
            total_debit += amt
        else:
            total_credit += amt
    if total_debit != total_credit:
        raise ValueError(
            f"Double-entry violation: debits ({total_debit}) != credits ({total_credit})"
        )

    # Validate accounts exist
    for s in splits:
        acct = db.query(Account).filter(Account.id == s["account_id"]).first()
        if acct is None:
            raise ValueError(f"Account {s['account_id']} not found")

    entry = RecurringEntry(
        name=name,
        description=description,
        reference_prefix=reference_prefix,
        frequency=freq,
        next_run_date=next_run_date,
        end_date=end_date,
        status=RecurringStatus.ACTIVE,
        created_by=user_id,
    )
    db.add(entry)
    db.flush()

    for s in splits:
        amt = Decimal(str(s["amount"]))
        is_debit = s["type"].lower() == "debit"
        db.add(RecurringEntrySplit(
            recurring_entry_id=entry.id,
            account_id=s["account_id"],
            debit_amount=amt if is_debit else Decimal("0"),
            credit_amount=amt if not is_debit else Decimal("0"),
        ))
    db.flush()

    log_action(
        db,
        user_id=user_id,
        action="RECURRING_ENTRY_CREATED",
        resource_type="recurring_entries",
        resource_id=str(entry.id),
        changes={"name": name, "frequency": frequency},
    )
    return entry


def update_recurring_entry(
    db: Session,
    *,
    entry_id: UUID,
    user_id: UUID,
    name: str | None = None,
    description: str | None = None,
    reference_prefix: str | None = None,
    frequency: str | None = None,
    next_run_date: date | None = None,
    end_date: date | None = None,
    splits: list[dict] | None = None,
) -> RecurringEntry:
    """Update an existing recurring entry. Does NOT commit."""
    entry = db.query(RecurringEntry).filter(RecurringEntry.id == entry_id).first()
    if entry is None:
        raise ValueError("Recurring entry not found")

    changes: dict = {}
    if name is not None:
        entry.name = name
        changes["name"] = name
    if description is not None:
        entry.description = description
        changes["description"] = description
    if reference_prefix is not None:
        entry.reference_prefix = reference_prefix
        changes["reference_prefix"] = reference_prefix
    if frequency is not None:
        try:
            entry.frequency = RecurringFrequency(frequency)
        except ValueError:
            raise ValueError(f"Invalid frequency: {frequency}")
        changes["frequency"] = frequency
    if next_run_date is not None:
        entry.next_run_date = next_run_date
        changes["next_run_date"] = next_run_date.isoformat()
    if end_date is not None:
        entry.end_date = end_date
        changes["end_date"] = end_date.isoformat()

    if splits is not None:
        # Validate double entry
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        for s in splits:
            amt = Decimal(str(s["amount"]))
            if amt <= 0:
                raise ValueError("Split amount must be greater than zero")
            if s["type"].lower() == "debit":
                total_debit += amt
            else:
                total_credit += amt
        if total_debit != total_credit:
            raise ValueError(
                f"Double-entry violation: debits ({total_debit}) != credits ({total_credit})"
            )

        # Replace splits
        for old_split in entry.splits:
            db.delete(old_split)
        db.flush()

        for s in splits:
            amt = Decimal(str(s["amount"]))
            is_debit = s["type"].lower() == "debit"
            db.add(RecurringEntrySplit(
                recurring_entry_id=entry.id,
                account_id=s["account_id"],
                debit_amount=amt if is_debit else Decimal("0"),
                credit_amount=amt if not is_debit else Decimal("0"),
            ))
        db.flush()
        changes["splits_replaced"] = True

    log_action(
        db,
        user_id=user_id,
        action="RECURRING_ENTRY_UPDATED",
        resource_type="recurring_entries",
        resource_id=str(entry.id),
        changes=changes,
    )
    return entry


def update_recurring_status(
    db: Session,
    *,
    entry_id: UUID,
    new_status: str,
    user_id: UUID,
) -> RecurringEntry:
    """Toggle ACTIVE / PAUSED. Does NOT commit."""
    entry = db.query(RecurringEntry).filter(RecurringEntry.id == entry_id).first()
    if entry is None:
        raise ValueError("Recurring entry not found")

    try:
        status = RecurringStatus(new_status)
    except ValueError:
        raise ValueError(f"Invalid status: {new_status}")

    old_status = entry.status.value
    entry.status = status
    db.flush()

    log_action(
        db,
        user_id=user_id,
        action="RECURRING_ENTRY_STATUS_CHANGED",
        resource_type="recurring_entries",
        resource_id=str(entry.id),
        changes={"old_status": old_status, "new_status": new_status},
    )
    return entry


def delete_recurring_entry(
    db: Session,
    *,
    entry_id: UUID,
    user_id: UUID,
) -> None:
    """Delete a recurring entry template. Does NOT commit."""
    entry = db.query(RecurringEntry).filter(RecurringEntry.id == entry_id).first()
    if entry is None:
        raise ValueError("Recurring entry not found")

    log_action(
        db,
        user_id=user_id,
        action="RECURRING_ENTRY_DELETED",
        resource_type="recurring_entries",
        resource_id=str(entry.id),
        changes={"name": entry.name},
    )
    db.delete(entry)
    db.flush()


def post_recurring_entry(
    db: Session,
    *,
    entry_id: UUID,
    user_id: UUID,
) -> dict:
    """Post a recurring entry: create a real JournalEntry and advance the schedule.

    ``create_journal_entry`` commits the journal entry internally.
    This function does NOT commit the recurring entry updates — caller must commit.
    Returns dict with journal_entry_id, next_run_date, total_posted.
    """
    entry = db.query(RecurringEntry).filter(RecurringEntry.id == entry_id).first()
    if entry is None:
        raise ValueError("Recurring entry not found")

    if entry.status != RecurringStatus.ACTIVE:
        raise ValueError("Cannot post a paused recurring entry")

    today = date.today()
    if entry.next_run_date > today:
        raise ValueError("This entry is not yet due for posting")

    if entry.end_date is not None and entry.next_run_date > entry.end_date:
        raise ValueError("This entry has passed its end date")

    # Build JournalEntryCreate from template splits
    je_splits: list[TransactionSplitCreate] = []
    for s in entry.splits:
        if s.debit_amount > 0:
            je_splits.append(TransactionSplitCreate(
                account_id=s.account_id,
                amount=s.debit_amount,
                type=SplitType.DEBIT,
            ))
        else:
            je_splits.append(TransactionSplitCreate(
                account_id=s.account_id,
                amount=s.credit_amount,
                type=SplitType.CREDIT,
            ))

    ref_prefix = entry.reference_prefix or "REC"
    reference = f"{ref_prefix}-{entry.next_run_date.year}-{entry.total_posted + 1:04d}"

    je_create = JournalEntryCreate(
        description=entry.description,
        reference=reference,
        splits=je_splits,
    )

    # This commits the journal entry internally
    journal = create_journal_entry(db, je_create, user_id)

    # Update recurring entry schedule
    entry.last_posted_at = datetime.now(timezone.utc)
    entry.total_posted += 1
    new_next = _advance_date(entry.next_run_date, entry.frequency)
    entry.next_run_date = new_next

    # Auto-pause if past end date
    if entry.end_date is not None and new_next > entry.end_date:
        entry.status = RecurringStatus.PAUSED

    db.flush()

    log_action(
        db,
        user_id=user_id,
        action="RECURRING_ENTRY_POSTED",
        resource_type="recurring_entries",
        resource_id=str(entry.id),
        changes={
            "journal_entry_id": str(journal.id),
            "next_run_date": new_next.isoformat(),
            "total_posted": entry.total_posted,
        },
    )

    return {
        "recurring_entry_id": str(entry.id),
        "journal_entry_id": str(journal.id),
        "next_run_date": new_next.isoformat(),
        "total_posted": entry.total_posted,
    }
