from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    JournalEntry,
    TransactionSplit,
)
from backend.app.models.invoice import CreditInvoice, InvoiceStatus
from backend.app.models.supplier import POStatus, PurchaseOrder, Supplier

ZERO = Decimal("0")
AR_ACCOUNT_CODE = "1300"
AP_ACCOUNT_CODE = "2100"
SALES_ACCOUNT_CODE = "4000"


def bucket(days_overdue: int) -> str:
    """Assign an aging bucket based on days overdue."""
    if days_overdue <= 30:
        return "current"
    elif days_overdue <= 60:
        return "days_31_60"
    elif days_overdue <= 90:
        return "days_61_90"
    else:
        return "over_90"


def empty_buckets() -> dict[str, Decimal]:
    return {
        "current": ZERO,
        "days_31_60": ZERO,
        "days_61_90": ZERO,
        "over_90": ZERO,
    }


def get_ar_aging(db: Session, as_of_date: date) -> dict:
    """Compute AR aging report from open/partial credit invoices."""
    as_of_dt = datetime(as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=timezone.utc)

    # Get all open/partial credit invoices
    invoices = (
        db.query(CreditInvoice)
        .filter(CreditInvoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.PARTIAL]))
        .all()
    )

    # Group by customer
    customer_data: dict[str, dict] = {}
    total_receivable = ZERO
    total_overdue = ZERO

    for inv in invoices:
        outstanding = Decimal(str(inv.total_amount)) - Decimal(str(inv.amount_paid))
        if outstanding <= ZERO:
            continue

        # Days overdue = days since due date (negative means not yet due → current)
        days_since_due = (as_of_dt - inv.due_date).days
        # If not yet due, put in current bucket; otherwise use days overdue
        days_overdue = max(0, days_since_due)
        bkt = bucket(days_overdue)

        cust_id = str(inv.customer_id)
        if cust_id not in customer_data:
            customer_data[cust_id] = {
                "name": inv.customer.name,
                "buckets": empty_buckets(),
            }

        customer_data[cust_id]["buckets"][bkt] += outstanding
        total_receivable += outstanding
        if days_since_due > 0:
            total_overdue += outstanding

    # DSO calculation: (total_receivable / total_credit_sales_365d) * 365
    # Total credit sales in last 365 days
    year_ago = as_of_dt - timedelta(days=365)
    credit_sales_365d = (
        db.query(sa_func.coalesce(sa_func.sum(CreditInvoice.total_amount), 0))
        .filter(CreditInvoice.invoice_date >= year_ago)
        .scalar()
    )
    credit_sales_365d = Decimal(str(credit_sales_365d))

    dso = ZERO
    if credit_sales_365d > ZERO:
        dso = (total_receivable / credit_sales_365d * 365).quantize(Decimal("0.1"))

    # Build rows
    customers_list = []
    grand_buckets = empty_buckets()

    for cust_id, data in sorted(customer_data.items(), key=lambda x: x[1]["name"]):
        b = data["buckets"]
        row_total = b["current"] + b["days_31_60"] + b["days_61_90"] + b["over_90"]
        customers_list.append(
            {
                "name": data["name"],
                "current": str(b["current"]),
                "days_31_60": str(b["days_31_60"]),
                "days_61_90": str(b["days_61_90"]),
                "over_90": str(b["over_90"]),
                "total": str(row_total),
            }
        )
        for k in grand_buckets:
            grand_buckets[k] += b[k]

    grand_total = sum(grand_buckets.values())
    totals_row = {
        "name": "Total",
        "current": str(grand_buckets["current"]),
        "days_31_60": str(grand_buckets["days_31_60"]),
        "days_61_90": str(grand_buckets["days_61_90"]),
        "over_90": str(grand_buckets["over_90"]),
        "total": str(grand_total),
    }

    return {
        "as_of_date": str(as_of_date),
        "kpi": {
            "total_receivable": str(total_receivable),
            "total_overdue": str(total_overdue),
            "dso": str(dso),
        },
        "customers": customers_list,
        "totals": totals_row,
    }


def _get_supplier_balance(db: Session, supplier_id: str) -> Decimal:
    """Outstanding balance for a supplier = received POs - payments."""
    from uuid import UUID

    sid = UUID(supplier_id)

    po_total = (
        db.query(sa_func.coalesce(sa_func.sum(PurchaseOrder.total_amount), 0))
        .filter(
            PurchaseOrder.supplier_id == sid,
            PurchaseOrder.status == POStatus.RECEIVED,
        )
        .scalar()
    )

    supplier_ref = f"SPAY-{supplier_id[:8].upper()}"
    ap_account = db.query(Account).filter(Account.code == AP_ACCOUNT_CODE).first()
    if not ap_account:
        return Decimal(str(po_total))

    payment_total = (
        db.query(sa_func.coalesce(sa_func.sum(TransactionSplit.debit_amount), 0))
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .filter(
            TransactionSplit.account_id == ap_account.id,
            JournalEntry.reference.like(f"{supplier_ref}%"),
        )
        .scalar()
    )

    return Decimal(str(po_total)) - Decimal(str(payment_total))


def get_ap_aging(db: Session, as_of_date: date) -> dict:
    """Compute AP aging report from supplier POs using FIFO allocation."""
    as_of_dt = datetime(as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=timezone.utc)

    # Get all suppliers with received POs
    suppliers = (
        db.query(Supplier)
        .join(PurchaseOrder)
        .filter(PurchaseOrder.status == POStatus.RECEIVED)
        .distinct()
        .all()
    )

    supplier_data: dict[str, dict] = {}
    total_payable = ZERO
    total_overdue = ZERO

    for supplier in suppliers:
        outstanding = _get_supplier_balance(db, str(supplier.id))
        if outstanding <= ZERO:
            continue

        # FIFO: distribute outstanding across received POs oldest-first
        pos = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.supplier_id == supplier.id,
                PurchaseOrder.status == POStatus.RECEIVED,
            )
            .order_by(PurchaseOrder.created_at.asc())
            .all()
        )

        buckets = empty_buckets()
        remaining = outstanding

        for po in pos:
            if remaining <= ZERO:
                break

            po_amount = min(Decimal(str(po.total_amount)), remaining)
            days_old = (as_of_dt - po.created_at).days
            days_old = max(0, days_old)
            bkt = bucket(days_old)
            buckets[bkt] += po_amount
            remaining -= po_amount

        # If remaining > 0 after all POs (edge case), put in over_90
        if remaining > ZERO:
            buckets["over_90"] += remaining

        row_total = sum(buckets.values())
        supplier_data[str(supplier.id)] = {
            "name": supplier.name,
            "buckets": buckets,
        }
        total_payable += row_total
        total_overdue += buckets["over_90"]

    # Build rows
    suppliers_list = []
    grand_buckets = empty_buckets()

    for sid, data in sorted(supplier_data.items(), key=lambda x: x[1]["name"]):
        b = data["buckets"]
        row_total = b["current"] + b["days_31_60"] + b["days_61_90"] + b["over_90"]
        suppliers_list.append(
            {
                "name": data["name"],
                "current": str(b["current"]),
                "days_31_60": str(b["days_31_60"]),
                "days_61_90": str(b["days_61_90"]),
                "over_90": str(b["over_90"]),
                "total": str(row_total),
            }
        )
        for k in grand_buckets:
            grand_buckets[k] += b[k]

    grand_total = sum(grand_buckets.values())
    totals_row = {
        "name": "Total",
        "current": str(grand_buckets["current"]),
        "days_31_60": str(grand_buckets["days_31_60"]),
        "days_61_90": str(grand_buckets["days_61_90"]),
        "over_90": str(grand_buckets["over_90"]),
        "total": str(grand_total),
    }

    return {
        "as_of_date": str(as_of_date),
        "kpi": {
            "total_payable": str(total_payable),
            "total_overdue": str(total_overdue),
        },
        "suppliers": suppliers_list,
        "totals": totals_row,
    }
