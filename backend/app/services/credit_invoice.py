from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    JournalEntry,
    TransactionSplit,
)
from backend.app.models.customer import Customer
from backend.app.models.inventory import Product
from backend.app.models.invoice import CreditInvoice, InvoicePayment, InvoiceStatus
from backend.app.services.audit import log_action

AR_ACCOUNT_CODE = "1300"
SALES_ACCOUNT_CODE = "4000"
VAT_PAYABLE_ACCOUNT_CODE = "2200"
COGS_ACCOUNT_CODE = "5000"
INVENTORY_ACCOUNT_CODE = "1100"
CASH_ACCOUNT_CODE = "1000"
BANK_ACCOUNT_CODE = "1200"

PAYMENT_METHOD_ACCOUNT_MAP: dict[str, str] = {
    "CASH": CASH_ACCOUNT_CODE,
    "CARD": BANK_ACCOUNT_CODE,
    "BANK_TRANSFER": BANK_ACCOUNT_CODE,
}

VAT_RATE = Decimal("15")
VAT_DIVISOR = Decimal("115")  # prices are VAT-inclusive
Q = Decimal("0.0001")
ZERO = Decimal("0")


def _get_account(db: Session, code: str) -> Account:
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        raise ValueError(f"Account {code} not found in chart of accounts")
    return account


def get_customer_ar_balance(db: Session, customer_id: UUID) -> Decimal:
    """Total outstanding AR for a customer (unpaid credit invoices)."""
    result = (
        db.query(
            sa_func.coalesce(
                sa_func.sum(CreditInvoice.total_amount - CreditInvoice.amount_paid),
                0,
            )
        )
        .filter(
            CreditInvoice.customer_id == customer_id,
            CreditInvoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.PARTIAL]),
        )
        .scalar()
    )
    return Decimal(str(result))


def create_credit_invoice(
    db: Session,
    customer_id: UUID,
    items: list[dict],
    user_id: UUID,
    invoice_date: datetime | None = None,
) -> dict:
    """Create a credit invoice with journal entries.

    items: list of {"product_id": UUID, "quantity": int}
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError("Customer not found")

    if not items:
        raise ValueError("Invoice must have at least one item")

    now = invoice_date or datetime.now(timezone.utc)

    # Compute line totals
    line_details: list[dict] = []
    for item in items:
        product = db.query(Product).filter(Product.id == item["product_id"]).first()
        if not product:
            raise ValueError(f"Product {item['product_id']} not found")

        qty = item["quantity"]
        if product.current_stock < qty:
            raise ValueError(
                f"Insufficient stock for '{product.name}': "
                f"{product.current_stock} available, {qty} requested"
            )

        line_total = (Decimal(str(product.unit_price)) * qty).quantize(
            Q, rounding=ROUND_HALF_UP
        )
        line_cost = (Decimal(str(product.cost_price)) * qty).quantize(
            Q, rounding=ROUND_HALF_UP
        )

        line_details.append(
            {
                "product": product,
                "quantity": qty,
                "line_total": line_total,
                "line_cost": line_cost,
                "unit_price": Decimal(str(product.unit_price)),
            }
        )

    grand_total = sum(ld["line_total"] for ld in line_details)
    total_cost = sum(ld["line_cost"] for ld in line_details)

    # VAT split (prices are VAT-inclusive)
    total_vat = (grand_total * VAT_RATE / VAT_DIVISOR).quantize(
        Q, rounding=ROUND_HALF_UP
    )
    total_net = grand_total - total_vat

    # Check credit limit
    if customer.credit_limit is not None:
        current_ar = get_customer_ar_balance(db, customer_id)
        if current_ar + grand_total > Decimal(str(customer.credit_limit)):
            raise ValueError(
                f"Credit limit exceeded. Limit: {customer.credit_limit}, "
                f"Current AR: {current_ar}, Invoice: {grand_total}"
            )

    # Generate invoice number: CINV-YYYY-NNNN
    year = now.year
    count = (
        db.query(CreditInvoice)
        .filter(CreditInvoice.invoice_number.like(f"CINV-{year}-%"))
        .count()
    )
    invoice_number = f"CINV-{year}-{count + 1:04d}"

    # Due date
    due_date = now + timedelta(days=customer.payment_terms_days)

    # Load accounts
    ar_account = _get_account(db, AR_ACCOUNT_CODE)
    sales_account = _get_account(db, SALES_ACCOUNT_CODE)
    vat_account = _get_account(db, VAT_PAYABLE_ACCOUNT_CODE)
    cogs_account = _get_account(db, COGS_ACCOUNT_CODE)
    inventory_account = _get_account(db, INVENTORY_ACCOUNT_CODE)

    # Journal entry
    item_count = len(line_details)
    description = (
        f"Credit Invoice {invoice_number}: "
        f"{line_details[0]['quantity']}x {line_details[0]['product'].name}"
        if item_count == 1
        else f"Credit Invoice {invoice_number}: {item_count} items"
    )

    journal = JournalEntry(
        entry_date=now,
        description=description,
        reference=invoice_number,
        created_by=user_id,
    )
    db.add(journal)
    db.flush()

    # DEBIT AR (1300) = grand total (VAT-inclusive)
    db.add(
        TransactionSplit(
            journal_entry_id=journal.id,
            account_id=ar_account.id,
            debit_amount=grand_total,
            credit_amount=ZERO,
        )
    )

    # CREDIT Sales Revenue (4000) = net amount
    db.add(
        TransactionSplit(
            journal_entry_id=journal.id,
            account_id=sales_account.id,
            debit_amount=ZERO,
            credit_amount=total_net,
        )
    )

    # CREDIT VAT Payable (2200) = VAT amount
    db.add(
        TransactionSplit(
            journal_entry_id=journal.id,
            account_id=vat_account.id,
            debit_amount=ZERO,
            credit_amount=total_vat,
        )
    )

    # Per-item: COGS + Inventory + stock deduction
    invoice_items: list[dict] = []
    for ld in line_details:
        product: Product = ld["product"]
        line_cost: Decimal = ld["line_cost"]

        # DEBIT COGS
        db.add(
            TransactionSplit(
                journal_entry_id=journal.id,
                account_id=cogs_account.id,
                debit_amount=line_cost,
                credit_amount=ZERO,
            )
        )
        # CREDIT Inventory
        db.add(
            TransactionSplit(
                journal_entry_id=journal.id,
                account_id=inventory_account.id,
                debit_amount=ZERO,
                credit_amount=line_cost,
            )
        )

        # Deduct stock
        product.current_stock -= ld["quantity"]

        invoice_items.append(
            {
                "product_name": product.name,
                "quantity": ld["quantity"],
                "unit_price": str(ld["unit_price"]),
                "line_total": str(ld["line_total"]),
            }
        )

    # Create CreditInvoice record
    credit_invoice = CreditInvoice(
        customer_id=customer_id,
        journal_entry_id=journal.id,
        invoice_number=invoice_number,
        invoice_date=now,
        due_date=due_date,
        total_amount=grand_total,
        amount_paid=ZERO,
        status=InvoiceStatus.OPEN,
    )
    db.add(credit_invoice)
    db.flush()

    log_action(
        db,
        user_id=user_id,
        action="CREDIT_INVOICE_CREATED",
        resource_type="credit_invoices",
        resource_id=str(credit_invoice.id),
        changes={
            "invoice_number": invoice_number,
            "customer": customer.name,
            "total_amount": str(grand_total),
            "due_date": due_date.isoformat(),
            "item_count": item_count,
        },
    )

    db.commit()

    return {
        "id": str(credit_invoice.id),
        "invoice_number": invoice_number,
        "customer_name": customer.name,
        "invoice_date": now.isoformat(),
        "due_date": due_date.isoformat(),
        "total_amount": str(grand_total),
        "net_amount": str(total_net),
        "vat_amount": str(total_vat),
        "status": InvoiceStatus.OPEN.value,
        "items": invoice_items,
        "journal_entry_id": str(journal.id),
    }


def record_invoice_payment(
    db: Session,
    invoice_id: UUID,
    amount: Decimal,
    payment_method: str,
    user_id: UUID,
    payment_date: datetime | None = None,
) -> dict:
    """Record a payment against a credit invoice."""
    invoice = db.query(CreditInvoice).filter(CreditInvoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Invoice not found")

    if invoice.status == InvoiceStatus.PAID:
        raise ValueError("Invoice is already fully paid")

    remaining = Decimal(str(invoice.total_amount)) - Decimal(str(invoice.amount_paid))
    if amount > remaining:
        raise ValueError(
            f"Payment amount ({amount}) exceeds remaining balance ({remaining})"
        )

    if payment_method not in PAYMENT_METHOD_ACCOUNT_MAP:
        raise ValueError(f"Invalid payment method: {payment_method}")

    now = payment_date or datetime.now(timezone.utc)

    # Load accounts
    ar_account = _get_account(db, AR_ACCOUNT_CODE)
    pay_account_code = PAYMENT_METHOD_ACCOUNT_MAP[payment_method]
    pay_account = _get_account(db, pay_account_code)

    # Journal entry: DEBIT Cash/Bank, CREDIT AR
    journal = JournalEntry(
        entry_date=now,
        description=f"Payment on {invoice.invoice_number}",
        reference=f"CPAY-{invoice.invoice_number}",
        created_by=user_id,
    )
    db.add(journal)
    db.flush()

    db.add(
        TransactionSplit(
            journal_entry_id=journal.id,
            account_id=pay_account.id,
            debit_amount=amount,
            credit_amount=ZERO,
        )
    )
    db.add(
        TransactionSplit(
            journal_entry_id=journal.id,
            account_id=ar_account.id,
            debit_amount=ZERO,
            credit_amount=amount,
        )
    )

    # Create InvoicePayment
    payment = InvoicePayment(
        invoice_id=invoice_id,
        journal_entry_id=journal.id,
        amount=amount,
        payment_date=now,
    )
    db.add(payment)

    # Update invoice
    new_paid = Decimal(str(invoice.amount_paid)) + amount
    invoice.amount_paid = new_paid
    if new_paid >= Decimal(str(invoice.total_amount)):
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIAL

    log_action(
        db,
        user_id=user_id,
        action="INVOICE_PAYMENT_RECORDED",
        resource_type="credit_invoices",
        resource_id=str(invoice.id),
        changes={
            "invoice_number": invoice.invoice_number,
            "payment_amount": str(amount),
            "new_total_paid": str(new_paid),
            "status": invoice.status.value,
            "payment_method": payment_method,
        },
    )

    db.commit()

    return {
        "payment_id": str(payment.id),
        "invoice_id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "amount": str(amount),
        "new_total_paid": str(new_paid),
        "remaining": str(Decimal(str(invoice.total_amount)) - new_paid),
        "status": invoice.status.value,
        "journal_entry_id": str(journal.id),
    }


def list_credit_invoices(
    db: Session,
    customer_id: UUID | None = None,
    status: str | None = None,
) -> list[dict]:
    """List credit invoices with optional filters."""
    query = db.query(CreditInvoice).join(Customer)

    if customer_id:
        query = query.filter(CreditInvoice.customer_id == customer_id)
    if status:
        query = query.filter(CreditInvoice.status == InvoiceStatus(status))

    invoices = query.order_by(CreditInvoice.created_at.desc()).all()

    return [
        {
            "id": str(inv.id),
            "customer_id": str(inv.customer_id),
            "customer_name": inv.customer.name,
            "invoice_number": inv.invoice_number,
            "invoice_date": inv.invoice_date.isoformat(),
            "due_date": inv.due_date.isoformat(),
            "total_amount": str(inv.total_amount),
            "amount_paid": str(inv.amount_paid),
            "status": inv.status.value,
        }
        for inv in invoices
    ]


def get_credit_invoice_detail(db: Session, invoice_id: UUID) -> dict:
    """Get full detail for a credit invoice including payments and line items."""
    invoice = db.query(CreditInvoice).filter(CreditInvoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Invoice not found")

    # Get line items from journal entry splits (COGS debits → products)
    journal = invoice.journal_entry
    items: list[dict] = []
    for split in journal.splits:
        if split.account.code == COGS_ACCOUNT_CODE and split.debit_amount > 0:
            items.append(
                {
                    "description": split.journal_entry.description,
                    "cost": str(split.debit_amount),
                }
            )

    payments = [
        {
            "id": str(p.id),
            "amount": str(p.amount),
            "payment_date": p.payment_date.isoformat(),
            "journal_entry_id": str(p.journal_entry_id),
        }
        for p in invoice.payments
    ]

    return {
        "id": str(invoice.id),
        "customer_id": str(invoice.customer_id),
        "customer_name": invoice.customer.name,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "total_amount": str(invoice.total_amount),
        "amount_paid": str(invoice.amount_paid),
        "status": invoice.status.value,
        "journal_entry_id": str(invoice.journal_entry_id),
        "payments": payments,
        "items": items,
    }
