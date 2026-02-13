from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    AccountType,
    JournalEntry,
    TransactionSplit,
)
from backend.app.services.audit import log_action
from backend.app.services.invoice import generate_expense_number

Q = Decimal("0.0001")
ZERO = Decimal("0")


def record_expense(
    db: Session,
    *,
    user_id: UUID,
    description: str,
    amount: Decimal,
    expense_account_id: UUID,
    payment_account_id: UUID,
    date: str | None = None,
    ip_address: str | None = None,
) -> dict:
    """Record an operational expense with a double-entry journal entry.

    DEBIT  Expense Account   (increases expense)
    CREDIT Payment Account   (decreases cash/bank)
    Reference: EXP-YYYY-NNNN
    """
    if amount <= ZERO:
        raise ValueError("Amount must be greater than 0")

    # Validate expense account
    expense_account = db.query(Account).filter(Account.id == expense_account_id).first()
    if not expense_account:
        raise ValueError("Expense account not found")
    if expense_account.account_type != AccountType.EXPENSE:
        raise ValueError(
            f"Account '{expense_account.name}' is not an EXPENSE account"
        )

    # Validate payment account
    payment_account = db.query(Account).filter(Account.id == payment_account_id).first()
    if not payment_account:
        raise ValueError("Payment account not found")
    if payment_account.account_type != AccountType.ASSET:
        raise ValueError(
            f"Account '{payment_account.name}' is not an ASSET account (Cash/Bank)"
        )

    # Determine entry date
    if date:
        entry_date = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    else:
        entry_date = datetime.now(timezone.utc)

    # Generate expense reference number
    exp_count = (
        db.query(JournalEntry)
        .filter(JournalEntry.reference.like("EXP-%"))
        .count()
    )
    reference = generate_expense_number(exp_count + 1, entry_date.year)

    # Quantize amount
    amt = Decimal(str(amount)).quantize(Q, rounding=ROUND_HALF_UP)

    # Create journal entry
    journal = JournalEntry(
        entry_date=entry_date,
        description=description,
        reference=reference,
        created_by=user_id,
    )
    db.add(journal)
    db.flush()

    # DEBIT Expense Account
    db.add(TransactionSplit(
        journal_entry_id=journal.id,
        account_id=expense_account.id,
        debit_amount=amt,
        credit_amount=ZERO,
    ))

    # CREDIT Payment Account
    db.add(TransactionSplit(
        journal_entry_id=journal.id,
        account_id=payment_account.id,
        debit_amount=ZERO,
        credit_amount=amt,
    ))

    # Audit log
    log_action(
        db,
        user_id=user_id,
        action="EXPENSE_RECORDED",
        resource_type="expenses",
        resource_id=reference,
        ip_address=ip_address,
        changes={
            "reference": reference,
            "description": description,
            "amount": str(amt),
            "expense_account": expense_account.name,
            "payment_account": payment_account.name,
            "journal_entry_id": str(journal.id),
        },
    )

    db.commit()

    return {
        "id": str(journal.id),
        "reference": reference,
        "description": description,
        "amount": str(amt),
        "expense_account_id": str(expense_account.id),
        "expense_account_name": expense_account.name,
        "payment_account_id": str(payment_account.id),
        "payment_account_name": payment_account.name,
        "date": entry_date.isoformat(timespec="seconds"),
        "created_by": str(user_id),
    }


def list_expenses(db: Session) -> list[dict]:
    """Return recent expense journal entries, newest first."""
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.reference.like("EXP-%"))
        .order_by(JournalEntry.created_at.desc())
        .limit(100)
        .all()
    )

    result: list[dict] = []
    for entry in entries:
        # Find the debit split (expense account) and credit split (payment account)
        expense_split = None
        payment_split = None
        for split in entry.splits:
            if split.debit_amount > 0:
                expense_split = split
            elif split.credit_amount > 0:
                payment_split = split

        result.append({
            "id": str(entry.id),
            "reference": entry.reference,
            "description": entry.description,
            "amount": str(expense_split.debit_amount) if expense_split else "0",
            "expense_account_name": expense_split.account.name if expense_split else "",
            "payment_account_name": payment_split.account.name if payment_split else "",
            "date": entry.entry_date.isoformat(timespec="seconds"),
            "created_by": entry.created_by_user.username,
        })

    return result
