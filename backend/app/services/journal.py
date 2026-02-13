from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.accounting import AuditLog, JournalEntry, TransactionSplit
from backend.app.schemas.accounting import JournalEntryCreate, SplitType
from backend.app.services.fiscal_close import assert_period_open


def create_journal_entry(
    db: Session,
    entry: JournalEntryCreate,
    user_id: UUID,
) -> JournalEntry:
    entry_date = datetime.now(timezone.utc)
    assert_period_open(db, entry_date)

    journal = JournalEntry(
        entry_date=entry_date,
        description=entry.description,
        reference=entry.reference,
        created_by=user_id,
    )
    db.add(journal)
    db.flush()  # populate journal.id before creating splits

    for split in entry.splits:
        db.add(
            TransactionSplit(
                journal_entry_id=journal.id,
                account_id=split.account_id,
                debit_amount=split.amount if split.type == SplitType.DEBIT else Decimal("0"),
                credit_amount=split.amount if split.type == SplitType.CREDIT else Decimal("0"),
            )
        )

    db.add(
        AuditLog(
            table_name="journal_entries",
            record_id=str(journal.id),
            action="INSERT",
            changed_by=user_id,
            new_values={
                "description": entry.description,
                "reference": entry.reference,
                "splits": [
                    {
                        "account_id": str(s.account_id),
                        "amount": str(s.amount),
                        "type": s.type.value,
                    }
                    for s in entry.splits
                ],
            },
        )
    )

    db.commit()
    db.refresh(journal)
    return journal
