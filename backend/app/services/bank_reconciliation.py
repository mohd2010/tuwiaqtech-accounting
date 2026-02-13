from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, JournalEntry, TransactionSplit
from backend.app.models.banking import BankStatementLine, ReconciliationStatus
from backend.app.schemas.banking import BankStatementLineCreate
from backend.app.services.audit import log_action

BANK_ACCOUNT_CODE = "1200"
ZERO = Decimal("0")


def _get_bank_account(db: Session) -> Account:
    account = db.query(Account).filter(Account.code == BANK_ACCOUNT_CODE).first()
    if not account:
        raise ValueError(f"Bank account {BANK_ACCOUNT_CODE} not found in chart of accounts")
    return account


# ─── Statement Lines CRUD ────────────────────────────────────────────────────


def create_statement_lines(
    db: Session,
    lines: list[BankStatementLineCreate],
    user_id: UUID,
    ip_address: str | None = None,
) -> list[BankStatementLine]:
    """Bulk-insert bank statement lines as UNMATCHED."""
    created: list[BankStatementLine] = []
    for line in lines:
        bsl = BankStatementLine(
            statement_date=line.statement_date,
            description=line.description,
            amount=line.amount,
            reference=line.reference,
            status=ReconciliationStatus.UNMATCHED,
            created_by=user_id,
        )
        db.add(bsl)
        created.append(bsl)
    db.flush()

    log_action(
        db,
        user_id=user_id,
        action="BANK_STATEMENT_LINES_ADDED",
        resource_type="bank_statement_lines",
        resource_id="bulk",
        ip_address=ip_address,
        changes={"count": len(created)},
    )
    db.commit()
    return created


def list_statement_lines(
    db: Session,
    status: ReconciliationStatus | None = None,
) -> list[dict]:
    """Return all statement lines with optional status filter and matched journal info."""
    query = db.query(BankStatementLine).order_by(BankStatementLine.statement_date.desc())
    if status is not None:
        query = query.filter(BankStatementLine.status == status)
    lines = query.all()

    result: list[dict] = []
    for bsl in lines:
        matched_ref: str | None = None
        matched_date: str | None = None
        if bsl.matched_split_id:
            split = db.query(TransactionSplit).filter(
                TransactionSplit.id == bsl.matched_split_id
            ).first()
            if split:
                je = db.query(JournalEntry).filter(
                    JournalEntry.id == split.journal_entry_id
                ).first()
                if je:
                    matched_ref = je.reference
                    matched_date = je.entry_date.isoformat() if je.entry_date else None

        result.append({
            "id": bsl.id,
            "statement_date": bsl.statement_date.isoformat(),
            "description": bsl.description,
            "amount": str(bsl.amount),
            "reference": bsl.reference,
            "status": bsl.status.value,
            "matched_split_id": bsl.matched_split_id,
            "matched_journal_ref": matched_ref,
            "matched_journal_date": matched_date,
            "reconciled_by": bsl.reconciled_by,
            "reconciled_at": bsl.reconciled_at.isoformat() if bsl.reconciled_at else None,
            "created_at": bsl.created_at.isoformat() if bsl.created_at else None,
        })
    return result


# ─── Auto-Match ──────────────────────────────────────────────────────────────


def auto_match(db: Session, user_id: UUID) -> int:
    """Auto-match UNMATCHED statement lines to Bank account splits.

    Matching criteria:
    - Exact amount match (statement amount == split net amount)
    - Date proximity (within 3 days)
    - Bonus: reference text match
    """
    bank_account = _get_bank_account(db)
    unmatched_lines = (
        db.query(BankStatementLine)
        .filter(BankStatementLine.status == ReconciliationStatus.UNMATCHED)
        .all()
    )

    # Get all bank splits not already matched
    already_matched_ids = {
        bsl.matched_split_id
        for bsl in db.query(BankStatementLine).filter(
            BankStatementLine.matched_split_id.isnot(None)
        ).all()
    }

    bank_splits = (
        db.query(TransactionSplit)
        .filter(TransactionSplit.account_id == bank_account.id)
        .all()
    )
    available_splits = [s for s in bank_splits if s.id not in already_matched_ids]

    matched_count = 0
    used_split_ids: set[UUID] = set()

    for bsl in unmatched_lines:
        best_split = None
        best_score = -1

        for split in available_splits:
            if split.id in used_split_ids:
                continue

            # Net amount: debit - credit (positive = inflow to bank)
            net = split.debit_amount - split.credit_amount
            if net != bsl.amount:
                continue

            # Date proximity
            je = db.query(JournalEntry).filter(
                JournalEntry.id == split.journal_entry_id
            ).first()
            if not je:
                continue

            je_date = je.entry_date.date() if hasattr(je.entry_date, 'date') else je.entry_date
            date_diff = abs((je_date - bsl.statement_date).days)
            if date_diff > 3:
                continue

            score = 10 - date_diff  # Higher score for closer dates

            # Bonus for reference match
            if bsl.reference and je.reference and bsl.reference.lower() in je.reference.lower():
                score += 5

            if score > best_score:
                best_score = score
                best_split = split

        if best_split:
            bsl.matched_split_id = best_split.id
            bsl.status = ReconciliationStatus.MATCHED
            used_split_ids.add(best_split.id)
            matched_count += 1

    if matched_count > 0:
        db.commit()
    return matched_count


# ─── Manual Match / Unmatch ──────────────────────────────────────────────────


def manual_match(
    db: Session,
    statement_line_id: UUID,
    split_id: UUID,
    user_id: UUID,
    ip_address: str | None = None,
) -> None:
    """Manually match a statement line to a specific GL split on Bank account."""
    bank_account = _get_bank_account(db)
    bsl = db.query(BankStatementLine).filter(BankStatementLine.id == statement_line_id).first()
    if not bsl:
        raise ValueError("Statement line not found")
    if bsl.status == ReconciliationStatus.RECONCILED:
        raise ValueError("Cannot modify a reconciled line")

    split = db.query(TransactionSplit).filter(TransactionSplit.id == split_id).first()
    if not split:
        raise ValueError("Transaction split not found")
    if split.account_id != bank_account.id:
        raise ValueError("Split is not on the Bank account")

    bsl.matched_split_id = split.id
    bsl.status = ReconciliationStatus.MATCHED

    log_action(
        db,
        user_id=user_id,
        action="BANK_LINE_MATCHED",
        resource_type="bank_statement_lines",
        resource_id=str(bsl.id),
        ip_address=ip_address,
        changes={"split_id": str(split_id)},
    )
    db.commit()


def unmatch(
    db: Session,
    statement_line_id: UUID,
    user_id: UUID,
    ip_address: str | None = None,
) -> None:
    """Revert a MATCHED line back to UNMATCHED. Cannot unmatch RECONCILED."""
    bsl = db.query(BankStatementLine).filter(BankStatementLine.id == statement_line_id).first()
    if not bsl:
        raise ValueError("Statement line not found")
    if bsl.status == ReconciliationStatus.RECONCILED:
        raise ValueError("Cannot unmatch a reconciled line")
    if bsl.status == ReconciliationStatus.UNMATCHED:
        raise ValueError("Line is already unmatched")

    old_split_id = bsl.matched_split_id
    bsl.matched_split_id = None
    bsl.status = ReconciliationStatus.UNMATCHED

    log_action(
        db,
        user_id=user_id,
        action="BANK_LINE_UNMATCHED",
        resource_type="bank_statement_lines",
        resource_id=str(bsl.id),
        ip_address=ip_address,
        changes={"previous_split_id": str(old_split_id)},
    )
    db.commit()


# ─── Reconcile ───────────────────────────────────────────────────────────────


def reconcile_lines(
    db: Session,
    statement_line_ids: list[UUID],
    user_id: UUID,
    ip_address: str | None = None,
) -> int:
    """Mark MATCHED lines as RECONCILED with timestamp."""
    now = datetime.now(timezone.utc)
    count = 0
    for line_id in statement_line_ids:
        bsl = db.query(BankStatementLine).filter(BankStatementLine.id == line_id).first()
        if not bsl:
            raise ValueError(f"Statement line {line_id} not found")
        if bsl.status != ReconciliationStatus.MATCHED:
            raise ValueError(
                f"Statement line {line_id} is {bsl.status.value}, not MATCHED"
            )
        bsl.status = ReconciliationStatus.RECONCILED
        bsl.reconciled_by = user_id
        bsl.reconciled_at = now
        count += 1

    log_action(
        db,
        user_id=user_id,
        action="BANK_LINES_RECONCILED",
        resource_type="bank_statement_lines",
        resource_id="batch",
        ip_address=ip_address,
        changes={"count": count, "line_ids": [str(lid) for lid in statement_line_ids]},
    )
    db.commit()
    return count


# ─── Summary ─────────────────────────────────────────────────────────────────


def get_reconciliation_summary(db: Session) -> dict:
    """GL balance vs statement balance with counts by status."""
    bank_account = _get_bank_account(db)

    # GL balance = sum(debits) - sum(credits) on Bank account
    gl_result = (
        db.query(
            sa_func.coalesce(sa_func.sum(TransactionSplit.debit_amount), ZERO),
            sa_func.coalesce(sa_func.sum(TransactionSplit.credit_amount), ZERO),
        )
        .filter(TransactionSplit.account_id == bank_account.id)
        .first()
    )
    gl_balance = (gl_result[0] or ZERO) - (gl_result[1] or ZERO)

    # Statement balance = sum of all statement line amounts
    stmt_balance = (
        db.query(sa_func.coalesce(sa_func.sum(BankStatementLine.amount), ZERO))
        .scalar()
    ) or ZERO

    # Reconciled balance = sum of RECONCILED line amounts
    reconciled_balance = (
        db.query(sa_func.coalesce(sa_func.sum(BankStatementLine.amount), ZERO))
        .filter(BankStatementLine.status == ReconciliationStatus.RECONCILED)
        .scalar()
    ) or ZERO

    # Counts by status
    unmatched_count = db.query(BankStatementLine).filter(
        BankStatementLine.status == ReconciliationStatus.UNMATCHED
    ).count()
    matched_count = db.query(BankStatementLine).filter(
        BankStatementLine.status == ReconciliationStatus.MATCHED
    ).count()
    reconciled_count = db.query(BankStatementLine).filter(
        BankStatementLine.status == ReconciliationStatus.RECONCILED
    ).count()

    return {
        "gl_balance": str(gl_balance),
        "statement_balance": str(stmt_balance),
        "reconciled_balance": str(reconciled_balance),
        "unmatched_count": unmatched_count,
        "matched_count": matched_count,
        "reconciled_count": reconciled_count,
    }


# ─── Unreconciled Splits ─────────────────────────────────────────────────────


def list_unreconciled_splits(db: Session) -> list[dict]:
    """Return Bank account splits not yet matched to any statement line."""
    bank_account = _get_bank_account(db)

    already_matched_ids = {
        bsl.matched_split_id
        for bsl in db.query(BankStatementLine).filter(
            BankStatementLine.matched_split_id.isnot(None)
        ).all()
    }

    splits = (
        db.query(TransactionSplit)
        .filter(TransactionSplit.account_id == bank_account.id)
        .all()
    )

    result: list[dict] = []
    for s in splits:
        if s.id in already_matched_ids:
            continue
        je = db.query(JournalEntry).filter(JournalEntry.id == s.journal_entry_id).first()
        net = s.debit_amount - s.credit_amount
        result.append({
            "split_id": s.id,
            "journal_entry_id": s.journal_entry_id,
            "journal_ref": je.reference if je else None,
            "journal_date": je.entry_date.isoformat() if je else "",
            "description": je.description if je else "",
            "debit_amount": str(s.debit_amount),
            "credit_amount": str(s.credit_amount),
            "net_amount": str(net),
        })
    return result
