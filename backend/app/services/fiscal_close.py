"""Fiscal year close service.

Performs the closing process:
1. Calculates net income (Revenue - Expenses) for the fiscal year
2. Creates a closing journal entry that zeros out all P&L accounts
   into Retained Earnings (account 3000)
3. Records the fiscal close, locking the period from further entries

Does NOT call db.commit() — caller is responsible.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    AccountType,
    JournalEntry,
    TransactionSplit,
)
from backend.app.models.fiscal import FiscalClose
from backend.app.services.audit import log_action

ZERO = Decimal("0")
RETAINED_EARNINGS_CODE = "3000"


def list_fiscal_closes(db: Session) -> list[FiscalClose]:
    """Return all fiscal closes ordered by year descending."""
    return (
        db.query(FiscalClose)
        .order_by(FiscalClose.fiscal_year.desc())
        .all()
    )


def is_year_closed(db: Session, year: int) -> bool:
    """Check if a fiscal year has already been closed."""
    return (
        db.query(FiscalClose)
        .filter(FiscalClose.fiscal_year == year)
        .first()
        is not None
    )


def assert_period_open(db: Session, entry_date: datetime) -> None:
    """Raise ValueError if the date falls within a closed fiscal year.

    Call this before creating any journal entry to enforce period locks.
    """
    year = entry_date.year
    if is_year_closed(db, year):
        raise ValueError(
            f"Fiscal year {year} is closed. No entries allowed in closed periods."
        )


def _account_balances_for_year(
    db: Session,
    account_type: AccountType,
    year: int,
) -> list[tuple[Account, Decimal]]:
    """Get the net balance of each account of a given type for a fiscal year.

    Revenue accounts: balance = credit - debit (credit-normal)
    Expense accounts: balance = debit - credit (debit-normal)
    """
    start_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    rows = (
        db.query(
            Account,
            func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("total_debit"),
            func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("total_credit"),
        )
        .join(TransactionSplit, TransactionSplit.account_id == Account.id)
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .filter(
            Account.account_type == account_type,
            JournalEntry.entry_date >= start_dt,
            JournalEntry.entry_date < end_dt,
        )
        .group_by(Account.id)
        .all()
    )

    result: list[tuple[Account, Decimal]] = []
    for account, total_debit, total_credit in rows:
        d = Decimal(str(total_debit))
        c = Decimal(str(total_credit))
        if account_type in (AccountType.REVENUE, AccountType.LIABILITY, AccountType.EQUITY):
            balance = c - d  # credit-normal
        else:
            balance = d - c  # debit-normal (ASSET, EXPENSE)
        if balance != ZERO:
            result.append((account, balance))

    return result


def perform_fiscal_close(
    db: Session,
    *,
    fiscal_year: int,
    admin_id: UUID,
    notes: str | None = None,
) -> FiscalClose:
    """Close a fiscal year by creating a closing journal entry.

    The closing entry:
    - DEBIT each Revenue account (to zero it out)
    - CREDIT each Expense account (to zero it out)
    - Net difference goes to Retained Earnings (3000)

    Raises ValueError if:
    - Year is already closed
    - Year is the current year or in the future
    - Retained Earnings account (3000) doesn't exist
    - No P&L balances to close
    """
    # Validation
    current_year = date.today().year
    if fiscal_year >= current_year:
        raise ValueError(
            f"Cannot close fiscal year {fiscal_year}. "
            f"Only past years can be closed (current year: {current_year})."
        )

    if is_year_closed(db, fiscal_year):
        raise ValueError(f"Fiscal year {fiscal_year} is already closed.")

    # Check prior years are closed
    prior_open = (
        db.query(FiscalClose.fiscal_year)
        .filter(FiscalClose.fiscal_year < fiscal_year)
        .all()
    )
    closed_years = {r.fiscal_year for r in prior_open}
    # Check if there's any journal entry in a year before fiscal_year that isn't closed
    earliest_entry = (
        db.query(func.min(JournalEntry.entry_date))
        .scalar()
    )
    if earliest_entry:
        earliest_year = earliest_entry.year
        for y in range(earliest_year, fiscal_year):
            if y not in closed_years:
                # Check if there are actually entries in this year
                has_entries = (
                    db.query(JournalEntry.id)
                    .filter(
                        JournalEntry.entry_date >= datetime(y, 1, 1, tzinfo=timezone.utc),
                        JournalEntry.entry_date < datetime(y + 1, 1, 1, tzinfo=timezone.utc),
                    )
                    .first()
                )
                if has_entries:
                    raise ValueError(
                        f"Cannot close {fiscal_year}: fiscal year {y} must be closed first."
                    )

    # Get Retained Earnings account
    retained_earnings = (
        db.query(Account).filter(Account.code == RETAINED_EARNINGS_CODE).first()
    )
    if not retained_earnings:
        raise ValueError(
            f"Retained Earnings account ({RETAINED_EARNINGS_CODE}) not found. "
            "Please create it before performing fiscal close."
        )

    # Get P&L balances
    revenue_balances = _account_balances_for_year(db, AccountType.REVENUE, fiscal_year)
    expense_balances = _account_balances_for_year(db, AccountType.EXPENSE, fiscal_year)

    if not revenue_balances and not expense_balances:
        raise ValueError(f"No revenue or expense activity in fiscal year {fiscal_year}.")

    # Calculate net income
    total_revenue = sum(bal for _, bal in revenue_balances)
    total_expenses = sum(bal for _, bal in expense_balances)
    net_income = total_revenue - total_expenses

    # Build closing journal entry splits
    close_date = datetime(fiscal_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    journal = JournalEntry(
        entry_date=close_date,
        description=f"Fiscal year {fiscal_year} closing entry",
        reference=f"CLOSE-{fiscal_year}",
        created_by=admin_id,
    )
    db.add(journal)
    db.flush()

    # Close Revenue accounts: DEBIT to zero out credit-normal balances
    for account, balance in revenue_balances:
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=account.id,
            debit_amount=balance,
            credit_amount=ZERO,
        ))

    # Close Expense accounts: CREDIT to zero out debit-normal balances
    for account, balance in expense_balances:
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=account.id,
            debit_amount=ZERO,
            credit_amount=balance,
        ))

    # Net to Retained Earnings
    if net_income > ZERO:
        # Profit: CREDIT Retained Earnings
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=retained_earnings.id,
            debit_amount=ZERO,
            credit_amount=net_income,
        ))
    elif net_income < ZERO:
        # Loss: DEBIT Retained Earnings
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=retained_earnings.id,
            debit_amount=abs(net_income),
            credit_amount=ZERO,
        ))
    # If net_income == 0, revenue exactly equals expenses, no RE entry needed
    # but the revenue/expense accounts still need zeroing

    db.flush()

    # Record the fiscal close
    fiscal_close = FiscalClose(
        fiscal_year=fiscal_year,
        close_date=date(fiscal_year, 12, 31),
        closing_entry_id=journal.id,
        closed_by=admin_id,
        notes=notes,
    )
    db.add(fiscal_close)
    db.flush()

    log_action(
        db,
        user_id=admin_id,
        action="FISCAL_YEAR_CLOSED",
        resource_type="fiscal_closes",
        resource_id=str(fiscal_close.id),
        changes={
            "fiscal_year": fiscal_year,
            "net_income": str(net_income),
            "total_revenue": str(total_revenue),
            "total_expenses": str(total_expenses),
            "closing_entry_id": str(journal.id),
        },
    )

    return fiscal_close
