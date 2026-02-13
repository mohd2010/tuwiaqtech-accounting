from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.models.inventory import Product
from backend.app.models.quotes import Quote, QuoteItem, QuoteStatus
from backend.app.schemas.pos import SaleItem
from backend.app.services.audit import log_action
from backend.app.services.invoice import generate_quote_number
from backend.app.services.pos import process_sale

Q = Decimal("0.0001")
DEFAULT_EXPIRY_DAYS = 14


def create_quote(
    db: Session,
    *,
    customer_name: str,
    customer_vat: str | None,
    expiry_date: date | None,
    notes: str | None,
    items: list[dict],
    user_id: UUID,
    ip_address: str | None = None,
) -> dict:
    """Create a new price quotation. Does NOT touch stock or journal entries."""
    if not items:
        raise ValueError("Quote must have at least one item")

    # Validate products and calculate totals
    line_items: list[dict] = []
    grand_total = Decimal("0")

    for item in items:
        product = db.query(Product).filter(Product.id == item["product_id"]).first()
        if not product:
            raise ValueError(f"Product {item['product_id']} not found")

        unit_price = Decimal(str(item["unit_price"]))
        quantity = item["quantity"]
        line_total = (unit_price * quantity).quantize(Q, rounding=ROUND_HALF_UP)
        grand_total += line_total

        line_items.append({
            "product": product,
            "product_id": product.id,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        })

    # Generate quote number
    now = datetime.now(timezone.utc)
    quote_count = db.query(Quote).filter(Quote.quote_number.like("Q-%")).count()
    quote_number = generate_quote_number(quote_count + 1, now.year)

    # Default expiry: 14 days from now
    if expiry_date is None:
        expiry_date = (now + timedelta(days=DEFAULT_EXPIRY_DAYS)).date()

    # Create quote
    quote = Quote(
        quote_number=quote_number,
        customer_name=customer_name,
        customer_vat=customer_vat,
        status=QuoteStatus.DRAFT,
        expiry_date=expiry_date,
        total_amount=grand_total,
        notes=notes,
        created_by=user_id,
    )
    db.add(quote)
    db.flush()

    # Create quote items
    for li in line_items:
        db.add(QuoteItem(
            quote_id=quote.id,
            product_id=li["product_id"],
            quantity=li["quantity"],
            unit_price=li["unit_price"],
            line_total=li["line_total"],
        ))

    # Audit log
    log_action(
        db,
        user_id=user_id,
        action="QUOTE_CREATED",
        resource_type="quotes",
        resource_id=quote_number,
        ip_address=ip_address,
        changes={
            "quote_number": quote_number,
            "customer_name": customer_name,
            "total_amount": str(grand_total),
            "item_count": len(line_items),
        },
    )

    db.commit()

    return _quote_to_dict(db, quote)


def list_quotes(db: Session) -> list[dict]:
    """Return all quotes ordered by creation date descending."""
    quotes = (
        db.query(Quote)
        .order_by(desc(Quote.created_at))
        .all()
    )
    results: list[dict] = []
    for q in quotes:
        results.append({
            "id": str(q.id),
            "quote_number": q.quote_number,
            "customer_name": q.customer_name,
            "status": q.status.value,
            "expiry_date": q.expiry_date.isoformat(),
            "total_amount": str(q.total_amount),
            "item_count": len(q.items),
            "created_at": q.created_at.isoformat(timespec="seconds") if q.created_at else "",
        })
    return results


def get_quote(db: Session, quote_id: UUID) -> dict:
    """Get a single quote with all its items."""
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise ValueError("Quote not found")
    return _quote_to_dict(db, quote)


def update_quote_status(
    db: Session,
    quote_id: UUID,
    new_status: str,
    user_id: UUID,
    ip_address: str | None = None,
) -> dict:
    """Update a quote's status (SENT, ACCEPTED, REJECTED)."""
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise ValueError("Quote not found")

    if quote.status == QuoteStatus.CONVERTED:
        raise ValueError("Cannot change status of a converted quote")

    old_status = quote.status.value
    quote.status = QuoteStatus(new_status)

    log_action(
        db,
        user_id=user_id,
        action="QUOTE_STATUS_UPDATED",
        resource_type="quotes",
        resource_id=quote.quote_number,
        ip_address=ip_address,
        changes={
            "old_status": old_status,
            "new_status": new_status,
        },
    )

    db.commit()
    return _quote_to_dict(db, quote)


def convert_to_invoice(
    db: Session,
    quote_id: UUID,
    user_id: UUID,
    ip_address: str | None = None,
) -> dict:
    """Convert an ACCEPTED or SENT quote into a real POS sale/invoice.

    1. Validates quote status is ACCEPTED or SENT.
    2. Calls process_sale() with the quote's items and prices.
    3. Marks quote as CONVERTED and links the invoice number.
    """
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise ValueError("Quote not found")

    if quote.status not in (QuoteStatus.ACCEPTED, QuoteStatus.SENT):
        raise ValueError(
            f"Cannot convert quote with status '{quote.status.value}'. "
            "Only ACCEPTED or SENT quotes can be converted."
        )

    # Build SaleItem list from quote items
    sale_items: list[SaleItem] = []
    for qi in quote.items:
        sale_items.append(SaleItem(
            product_id=qi.product_id,
            quantity=qi.quantity,
        ))

    # Process the actual sale (creates journal entries, updates stock, etc.)
    invoice_data = process_sale(
        db=db,
        items=sale_items,
        user_id=user_id,
        ip_address=ip_address,
    )

    # Mark quote as converted and link invoice
    # Note: process_sale already committed, so we need a fresh transaction
    quote.status = QuoteStatus.CONVERTED
    quote.invoice_number = invoice_data["invoice_number"]

    log_action(
        db,
        user_id=user_id,
        action="QUOTE_CONVERTED",
        resource_type="quotes",
        resource_id=quote.quote_number,
        ip_address=ip_address,
        changes={
            "quote_number": quote.quote_number,
            "invoice_number": invoice_data["invoice_number"],
        },
    )

    db.commit()

    return {
        "quote_id": str(quote.id),
        "quote_number": quote.quote_number,
        "invoice_number": invoice_data["invoice_number"],
        "invoice_data": invoice_data,
    }


def _quote_to_dict(db: Session, quote: Quote) -> dict:
    """Convert a Quote ORM object to a response dict."""
    items_out: list[dict] = []
    for qi in quote.items:
        product = db.query(Product).filter(Product.id == qi.product_id).first()
        items_out.append({
            "id": str(qi.id),
            "product_id": str(qi.product_id),
            "product_name": product.name if product else "Unknown",
            "quantity": qi.quantity,
            "unit_price": str(qi.unit_price),
            "line_total": str(qi.line_total),
        })

    return {
        "id": str(quote.id),
        "quote_number": quote.quote_number,
        "customer_name": quote.customer_name,
        "customer_vat": quote.customer_vat,
        "status": quote.status.value,
        "expiry_date": quote.expiry_date.isoformat(),
        "total_amount": str(quote.total_amount),
        "notes": quote.notes,
        "invoice_number": quote.invoice_number,
        "created_by": str(quote.created_by),
        "created_at": quote.created_at.isoformat(timespec="seconds") if quote.created_at else "",
        "items": items_out,
    }
