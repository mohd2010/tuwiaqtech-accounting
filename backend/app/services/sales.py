from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.models.accounting import JournalEntry, User
from backend.app.models.customer import Customer, Sale
from backend.app.models.inventory import Product
from backend.app.models.pos import SaleDiscount
from backend.app.models.returns import CreditNote, CreditNoteStatus
from backend.app.services.invoice import (
    SELLER_NAME,
    VAT_REGISTRATION_NUMBER,
    generate_zatca_qr,
)

VAT_RATE = Decimal("15")
VAT_DIVISOR = Decimal("115")
Q = Decimal("0.0001")


def list_sales(db: Session) -> list[dict]:
    """Return all POS sales (INV-% journal entries) with status and customer info."""
    journals = (
        db.query(JournalEntry)
        .filter(JournalEntry.reference.like("INV-%"))
        .order_by(desc(JournalEntry.created_at))
        .all()
    )

    results: list[dict] = []
    for journal in journals:
        # Get sale line items
        sales = (
            db.query(Sale)
            .filter(Sale.journal_entry_id == journal.id)
            .all()
        )
        if not sales:
            continue

        # Customer name
        customer_name: str | None = None
        if sales[0].customer_id:
            customer = db.query(Customer).filter(Customer.id == sales[0].customer_id).first()
            if customer:
                customer_name = customer.name

        # Cashier username
        cashier = db.query(User).filter(User.id == journal.created_by).first()
        cashier_name = cashier.username if cashier else "Unknown"

        # Total amount (sum of all sale line totals = original total before discount)
        total_amount = sum(Decimal(str(s.total_amount)) for s in sales)

        # Check for discount
        sale_discount = db.query(SaleDiscount).filter(
            SaleDiscount.journal_entry_id == journal.id
        ).first()
        discount_amount = Decimal(str(sale_discount.discount_amount)) if sale_discount else Decimal("0")

        # Actual total (what customer paid) = original - discount
        actual_total = total_amount - discount_amount

        # VAT breakdown on actual total
        vat_amount = (actual_total * VAT_RATE / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)
        net_amount = actual_total - vat_amount

        # Item count
        item_count = sum(s.quantity for s in sales)

        # Check if any return (credit note) exists for this invoice
        has_return = (
            db.query(CreditNote)
            .filter(
                CreditNote.original_journal_entry_id == journal.id,
                CreditNote.status == CreditNoteStatus.ISSUED,
            )
            .first()
            is not None
        )

        results.append({
            "id": str(journal.id),
            "invoice_number": journal.reference,
            "date": journal.created_at.isoformat(timespec="seconds") if journal.created_at else journal.entry_date.isoformat(timespec="seconds"),
            "customer_name": customer_name,
            "cashier": cashier_name,
            "item_count": item_count,
            "total_amount": str(actual_total),
            "net_amount": str(net_amount),
            "vat_amount": str(vat_amount),
            "status": "RETURNED" if has_return else "PAID",
            "discount_amount": str(discount_amount),
        })

    return results


def get_sale_detail(db: Session, invoice_number: str) -> dict:
    """Get full invoice detail for reprinting a receipt."""
    journal = (
        db.query(JournalEntry)
        .filter(JournalEntry.reference == invoice_number)
        .first()
    )
    if not journal:
        raise ValueError(f"Invoice {invoice_number} not found")

    sales = (
        db.query(Sale)
        .filter(Sale.journal_entry_id == journal.id)
        .all()
    )
    if not sales:
        raise ValueError(f"No sale items found for {invoice_number}")

    # Build line items
    items: list[dict] = []
    grand_total = Decimal("0")
    for sale in sales:
        product = db.query(Product).filter(Product.id == sale.product_id).first()
        if not product:
            continue
        line_total = Decimal(str(sale.total_amount))
        grand_total += line_total
        unit_price = Decimal(str(product.unit_price))

        items.append({
            "product": product.name,
            "quantity": sale.quantity,
            "unit_price": str(unit_price),
            "line_total": str(line_total),
        })

    # Check for discount
    sale_discount = db.query(SaleDiscount).filter(
        SaleDiscount.journal_entry_id == journal.id
    ).first()
    discount_amount = Decimal(str(sale_discount.discount_amount)) if sale_discount else Decimal("0")
    original_total = grand_total
    actual_total = grand_total - discount_amount

    vat_amount = (actual_total * VAT_RATE / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)
    net_revenue = actual_total - vat_amount

    # Regenerate ZATCA QR
    timestamp = journal.created_at or journal.entry_date
    qr_code = generate_zatca_qr(
        seller_name=SELLER_NAME,
        vat_number=VAT_REGISTRATION_NUMBER,
        timestamp=timestamp,
        total_amount=str(actual_total),
        vat_amount=str(vat_amount),
    )

    return {
        "invoice_number": invoice_number,
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "journal_entry_id": str(journal.id),
        "items": items,
        "total_collected": str(actual_total),
        "net_revenue": str(net_revenue),
        "vat_amount": str(vat_amount),
        "qr_code": qr_code,
        "discount_amount": str(discount_amount),
        "original_total": str(original_total) if discount_amount > Decimal("0") else "",
    }
