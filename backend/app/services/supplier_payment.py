from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    JournalEntry,
    TransactionSplit,
)
from backend.app.models.supplier import POStatus, PurchaseOrder, Supplier
from backend.app.services.audit import log_action

AP_ACCOUNT_CODE = "2100"


def _get_account(db: Session, code: str) -> Account:
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        raise ValueError(f"Account {code} not found in chart of accounts")
    return account


def get_supplier_balance(db: Session, supplier_id: UUID) -> Decimal:
    """Outstanding balance = total of received POs credited to AP for this supplier
    minus total payments (debits to AP referencing this supplier).

    We compute this from the AP account's transaction splits linked to
    journal entries whose reference contains the supplier id or PO id.
    Simpler approach: sum received PO amounts - sum payment amounts.
    """
    # Total from received POs
    po_total = (
        db.query(func.coalesce(func.sum(PurchaseOrder.total_amount), 0))
        .filter(
            PurchaseOrder.supplier_id == supplier_id,
            PurchaseOrder.status == POStatus.RECEIVED,
        )
        .scalar()
    )

    # Total payments made (journal entries with reference like "SPAY-{supplier_id}")
    supplier_ref = f"SPAY-{str(supplier_id)[:8].upper()}"
    payment_total = (
        db.query(func.coalesce(func.sum(TransactionSplit.debit_amount), 0))
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .join(Account, TransactionSplit.account_id == Account.id)
        .filter(
            Account.code == AP_ACCOUNT_CODE,
            JournalEntry.reference.like(f"{supplier_ref}%"),
        )
        .scalar()
    )

    return Decimal(str(po_total)) - Decimal(str(payment_total))


def pay_supplier_invoice(
    db: Session,
    supplier_id: UUID,
    amount: Decimal,
    payment_account_id: UUID,
    user_id: UUID,
) -> dict[str, str]:
    """Pay a supplier: DEBIT Accounts Payable, CREDIT payment account (Cash/Bank)."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise ValueError("Supplier not found")

    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero")

    ap_account = _get_account(db, AP_ACCOUNT_CODE)

    # Verify payment account exists
    payment_account = db.query(Account).filter(Account.id == payment_account_id).first()
    if not payment_account:
        raise ValueError("Payment account not found")

    now = datetime.now(timezone.utc)
    supplier_ref = f"SPAY-{str(supplier_id)[:8].upper()}"

    journal = JournalEntry(
        entry_date=now,
        description=f"Payment to Supplier: {supplier.name}",
        reference=f"{supplier_ref}-{now.strftime('%Y%m%d%H%M%S')}",
        created_by=user_id,
    )
    db.add(journal)
    db.flush()

    # DEBIT Accounts Payable (reduce liability)
    db.add(TransactionSplit(
        journal_entry_id=journal.id,
        account_id=ap_account.id,
        debit_amount=amount,
        credit_amount=Decimal("0"),
    ))
    # CREDIT Cash/Bank (reduce asset)
    db.add(TransactionSplit(
        journal_entry_id=journal.id,
        account_id=payment_account.id,
        debit_amount=Decimal("0"),
        credit_amount=amount,
    ))

    log_action(
        db,
        user_id=user_id,
        action="SUPPLIER_PAYMENT",
        resource_type="suppliers",
        resource_id=str(supplier.id),
        changes={
            "supplier": supplier.name,
            "amount": str(amount),
            "payment_account_id": str(payment_account_id),
            "journal_entry_id": str(journal.id),
        },
    )

    db.commit()

    return {
        "journal_entry_id": str(journal.id),
        "supplier": supplier.name,
        "amount": str(amount),
        "payment_account": f"{payment_account.code} - {payment_account.name}",
    }
