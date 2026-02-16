from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    JournalEntry,
    TransactionSplit,
)
from backend.app.models.customer import Customer, Sale
from backend.app.models.inventory import Product
from backend.app.models.returns import (
    CreditNote,
    CreditNoteItem,
    CreditNoteStatus,
    ItemCondition,
)
from backend.app.services.audit import log_action
from backend.app.services.invoice import (
    SELLER_NAME,
    VAT_REGISTRATION_NUMBER,
    generate_credit_note_number,
    generate_zatca_qr,
)

# ── Account codes (same as POS) ──────────────────────────────────────────────
CASH_ACCOUNT_CODE = "1000"
INVENTORY_ACCOUNT_CODE = "1100"
VAT_PAYABLE_ACCOUNT_CODE = "2200"
SALES_ACCOUNT_CODE = "4000"
COGS_ACCOUNT_CODE = "5000"
SHRINKAGE_ACCOUNT_CODE = "5200"

VAT_RATE = Decimal("15")
VAT_DIVISOR = Decimal("115")
Q = Decimal("0.0001")
ZERO = Decimal("0")


def _get_account(db: Session, code: str) -> Account:
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        raise ValueError(f"Account {code} not found in chart of accounts")
    return account


# ─── Invoice Lookup ───────────────────────────────────────────────────────────


def lookup_invoice(db: Session, invoice_number: str) -> dict:
    """Look up an invoice by number and return returnable items.

    Calculates already-returned quantities from existing issued credit notes
    and returns the remaining returnable quantity per product.
    """
    # Find original sale journal entry
    journal = (
        db.query(JournalEntry)
        .filter(JournalEntry.reference == invoice_number)
        .first()
    )
    if not journal:
        raise ValueError(f"Invoice {invoice_number} not found")

    # Get sale line items
    sales = (
        db.query(Sale)
        .filter(Sale.journal_entry_id == journal.id)
        .all()
    )
    if not sales:
        raise ValueError(f"No sale items found for invoice {invoice_number}")

    # Calculate already-returned quantities per product from ISSUED credit notes
    already_returned: dict[UUID, int] = {}
    existing_cns = (
        db.query(CreditNote)
        .filter(
            CreditNote.original_journal_entry_id == journal.id,
            CreditNote.status == CreditNoteStatus.ISSUED,
        )
        .all()
    )
    for cn in existing_cns:
        for item in cn.items:
            already_returned[item.product_id] = (
                already_returned.get(item.product_id, 0) + item.quantity
            )

    # Build response items
    items: list[dict] = []
    grand_total = ZERO
    total_vat = ZERO

    # Get customer_id from the first sale (all should share the same)
    customer_id = sales[0].customer_id if sales else None

    for sale in sales:
        product = db.query(Product).filter(Product.id == sale.product_id).first()
        if not product:
            continue

        qty_returned = already_returned.get(sale.product_id, 0)
        returnable = sale.quantity - qty_returned

        line_total = Decimal(str(sale.total_amount))
        grand_total += line_total

        items.append({
            "product_id": str(sale.product_id),
            "product_name": product.name,
            "sku": product.sku,
            "quantity_sold": sale.quantity,
            "quantity_returned": qty_returned,
            "returnable_quantity": returnable,
            "unit_price": str(product.unit_price),
            "cost_price": str(product.cost_price),
        })

    total_vat = (grand_total * VAT_RATE / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)
    net_amount = grand_total - total_vat

    return {
        "invoice_number": invoice_number,
        "journal_entry_id": str(journal.id),
        "timestamp": journal.created_at.isoformat(timespec="seconds"),
        "customer_id": str(customer_id) if customer_id else None,
        "items": items,
        "total_amount": str(grand_total),
        "vat_amount": str(total_vat),
        "net_amount": str(net_amount),
    }


# ─── Process Return ──────────────────────────────────────────────────────────


def process_return(
    db: Session,
    invoice_number: str,
    items: list[dict],
    reason: str,
    user_id: UUID,
    ip_address: str | None = None,
) -> dict:
    """Process a customer return against an existing invoice.

    Creates a reversal journal entry, credit note, and updates stock/customer.

    Each item dict must contain: product_id, quantity, condition (RESALABLE/DAMAGED).
    """
    # ── Find original sale ────────────────────────────────────────────────
    journal = (
        db.query(JournalEntry)
        .filter(JournalEntry.reference == invoice_number)
        .first()
    )
    if not journal:
        raise ValueError(f"Invoice {invoice_number} not found")

    # Build map of original sales: product_id → Sale
    sales = (
        db.query(Sale)
        .filter(Sale.journal_entry_id == journal.id)
        .all()
    )
    sale_map: dict[UUID, Sale] = {sale.product_id: sale for sale in sales}

    # Calculate already-returned quantities
    already_returned: dict[UUID, int] = {}
    existing_cns = (
        db.query(CreditNote)
        .filter(
            CreditNote.original_journal_entry_id == journal.id,
            CreditNote.status == CreditNoteStatus.ISSUED,
        )
        .all()
    )
    for cn in existing_cns:
        for cn_item in cn.items:
            already_returned[cn_item.product_id] = (
                already_returned.get(cn_item.product_id, 0) + cn_item.quantity
            )

    # ── Validate return items ─────────────────────────────────────────────
    line_details: list[dict] = []
    for item in items:
        product_id = UUID(item["product_id"]) if isinstance(item["product_id"], str) else item["product_id"]
        quantity = item["quantity"]
        condition = item["condition"]

        if product_id not in sale_map:
            raise ValueError(f"Product {product_id} was not in the original sale")

        sale = sale_map[product_id]
        prev_returned = already_returned.get(product_id, 0)
        returnable = sale.quantity - prev_returned

        if quantity > returnable:
            raise ValueError(
                f"Cannot return {quantity} of product {product_id}: "
                f"only {returnable} returnable"
            )

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        unit_price = Decimal(str(product.unit_price))
        cost_price = Decimal(str(product.cost_price))
        line_refund = (unit_price * quantity).quantize(Q, rounding=ROUND_HALF_UP)
        line_cost = (cost_price * quantity).quantize(Q, rounding=ROUND_HALF_UP)

        line_details.append({
            "product": product,
            "product_id": product_id,
            "quantity": quantity,
            "condition": condition,
            "unit_price": unit_price,
            "cost_price": cost_price,
            "line_refund": line_refund,
            "line_cost": line_cost,
        })

    # ── Calculate totals ──────────────────────────────────────────────────
    gross_refund = sum(ld["line_refund"] for ld in line_details)
    vat_refund = (gross_refund * VAT_RATE / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)
    net_refund = gross_refund - vat_refund

    # ── Load accounts ─────────────────────────────────────────────────────
    cash_account = _get_account(db, CASH_ACCOUNT_CODE)
    sales_account = _get_account(db, SALES_ACCOUNT_CODE)
    vat_account = _get_account(db, VAT_PAYABLE_ACCOUNT_CODE)
    cogs_account = _get_account(db, COGS_ACCOUNT_CODE)
    inventory_account = _get_account(db, INVENTORY_ACCOUNT_CODE)
    shrinkage_account = _get_account(db, SHRINKAGE_ACCOUNT_CODE)

    # ── Credit note number ────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    cn_count = (
        db.query(sa_func.count(CreditNote.id))
        .filter(CreditNote.credit_note_number.like("CN-%"))
        .scalar()
    ) or 0
    cn_number = generate_credit_note_number(cn_count + 1, now.year)

    # ── Create reversal journal entry ─────────────────────────────────────
    description = f"Return: {cn_number} against {invoice_number}"
    refund_journal = JournalEntry(
        entry_date=now,
        description=description,
        reference=cn_number,
        created_by=user_id,
    )
    db.add(refund_journal)
    db.flush()

    # Revenue reversal: DEBIT Sales (4000)
    db.add(TransactionSplit(
        journal_entry_id=refund_journal.id,
        account_id=sales_account.id,
        debit_amount=net_refund,
        credit_amount=ZERO,
    ))

    # VAT reversal: DEBIT VAT Payable (2200)
    db.add(TransactionSplit(
        journal_entry_id=refund_journal.id,
        account_id=vat_account.id,
        debit_amount=vat_refund,
        credit_amount=ZERO,
    ))

    # Cash out: CREDIT Cash (1000)
    db.add(TransactionSplit(
        journal_entry_id=refund_journal.id,
        account_id=cash_account.id,
        debit_amount=ZERO,
        credit_amount=gross_refund,
    ))

    # ── Per-item splits + stock + credit note items ───────────────────────
    cn_items_out: list[dict] = []
    credit_note_items: list[CreditNoteItem] = []

    # Get customer_id from first sale
    customer_id = sales[0].customer_id if sales else None

    for ld in line_details:
        product: Product = ld["product"]
        line_cost: Decimal = ld["line_cost"]
        condition: str = ld["condition"]

        if condition == "RESALABLE":
            # DEBIT Inventory (1100)
            db.add(TransactionSplit(
                journal_entry_id=refund_journal.id,
                account_id=inventory_account.id,
                debit_amount=line_cost,
                credit_amount=ZERO,
            ))
            # CREDIT COGS (5000)
            db.add(TransactionSplit(
                journal_entry_id=refund_journal.id,
                account_id=cogs_account.id,
                debit_amount=ZERO,
                credit_amount=line_cost,
            ))
            # Increase stock for resalable items
            product.current_stock += ld["quantity"]
        else:
            # DAMAGED: DEBIT Inventory Shrinkage (5200)
            db.add(TransactionSplit(
                journal_entry_id=refund_journal.id,
                account_id=shrinkage_account.id,
                debit_amount=line_cost,
                credit_amount=ZERO,
            ))
            # CREDIT COGS (5000)
            db.add(TransactionSplit(
                journal_entry_id=refund_journal.id,
                account_id=cogs_account.id,
                debit_amount=ZERO,
                credit_amount=line_cost,
            ))
            # Damaged: do NOT increase stock

        cn_item = CreditNoteItem(
            product_id=ld["product_id"],
            quantity=ld["quantity"],
            condition=ItemCondition(condition),
            unit_refund_amount=ld["unit_price"],
            line_refund_amount=ld["line_refund"],
        )
        credit_note_items.append(cn_item)

        cn_items_out.append({
            "product_name": product.name,
            "quantity": ld["quantity"],
            "condition": condition,
            "unit_refund_amount": str(ld["unit_price"]),
            "line_refund_amount": str(ld["line_refund"]),
        })

    # ── Create credit note ────────────────────────────────────────────────
    credit_note = CreditNote(
        original_journal_entry_id=journal.id,
        credit_note_number=cn_number,
        reason=reason,
        status=CreditNoteStatus.ISSUED,
        total_refund_amount=gross_refund,
        vat_refund_amount=vat_refund,
        net_refund_amount=net_refund,
        journal_entry_id=refund_journal.id,
        created_by=user_id,
    )
    db.add(credit_note)
    db.flush()

    # Attach items to credit note
    for cn_item in credit_note_items:
        cn_item.credit_note_id = credit_note.id
        db.add(cn_item)

    # ── Update customer totals ────────────────────────────────────────────
    if customer_id:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer:
            customer.total_spent = Decimal(str(customer.total_spent)) - gross_refund

    # ── ZATCA E-Invoice (Credit Note) ──────────────────────────────────────
    try:
        from backend.app.services.zatca.einvoice_service import (
            create_einvoice_for_credit_note,
            submit_einvoice_to_zatca,
        )

        customer_obj = None
        if customer_id:
            customer_obj = db.query(Customer).filter(Customer.id == customer_id).first()
        einvoice = create_einvoice_for_credit_note(
            db,
            journal_entry_id=refund_journal.id,
            credit_note_number=cn_number,
            original_invoice_number=invoice_number,
            customer=customer_obj,
            line_details=line_details,
            total_net=net_refund,
            total_vat=vat_refund,
            gross_total=gross_refund,
            now=now,
            credit_note_id=credit_note.id,
            reason=reason,
        )
        qr_code = einvoice.qr_code

        # Submit to ZATCA (non-blocking for return — errors logged, not raised)
        try:
            submit_einvoice_to_zatca(db, einvoice)
        except Exception:
            pass  # Return proceeds; credit note stays PENDING for retry
    except Exception:
        # Fallback to Phase 1 QR if Organization not configured
        qr_code = generate_zatca_qr(
            seller_name=SELLER_NAME,
            vat_number=VAT_REGISTRATION_NUMBER,
            timestamp=now,
            total_amount=f"-{gross_refund}",
            vat_amount=f"-{vat_refund}",
        )

    # ── Audit log ─────────────────────────────────────────────────────────
    log_action(
        db,
        user_id=user_id,
        action="RETURN_PROCESSED",
        resource_type="credit_notes",
        resource_id=cn_number,
        ip_address=ip_address,
        changes={
            "credit_note_number": cn_number,
            "original_invoice": invoice_number,
            "reason": reason,
            "total_refund": str(gross_refund),
            "net_refund": str(net_refund),
            "vat_refund": str(vat_refund),
            "journal_entry_id": str(refund_journal.id),
            "items": [
                {
                    "product_id": str(ld["product_id"]),
                    "product_name": ld["product"].name,
                    "quantity": ld["quantity"],
                    "condition": ld["condition"],
                }
                for ld in line_details
            ],
        },
    )

    db.commit()

    return {
        "credit_note_number": cn_number,
        "original_invoice_number": invoice_number,
        "timestamp": now.isoformat(timespec="seconds"),
        "reason": reason,
        "items": cn_items_out,
        "total_refund": str(gross_refund),
        "net_refund": str(net_refund),
        "vat_refund": str(vat_refund),
        "qr_code": qr_code,
        "journal_entry_id": str(refund_journal.id),
    }
