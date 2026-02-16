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
    User,
)
from backend.app.models.customer import Customer, Sale
from backend.app.models.inventory import Product, WarehouseStock
from backend.app.models.pos import DiscountType, PaymentMethod, Register, SaleDiscount, SalePayment, Shift, ShiftStatus
from backend.app.schemas.pos import PaymentEntry, ShiftOut
from backend.app.schemas.pos import SaleItem
from backend.app.services.audit import log_action
from backend.app.services.invoice import (
    SELLER_NAME,
    VAT_REGISTRATION_NUMBER,
    generate_invoice_number,
    generate_zatca_qr,
)

CASH_ACCOUNT_CODE = "1000"
BANK_ACCOUNT_CODE = "1200"
INVENTORY_ACCOUNT_CODE = "1100"
VAT_PAYABLE_ACCOUNT_CODE = "2200"
SALES_ACCOUNT_CODE = "4000"
COGS_ACCOUNT_CODE = "5000"
CASH_SHORTAGE_ACCOUNT_CODE = "5300"
OTHER_INCOME_ACCOUNT_CODE = "4200"
DISCOUNT_ACCOUNT_CODE = "4100"

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


def process_sale(
    db: Session,
    items: list[SaleItem],
    user_id: UUID,
    customer_id: UUID | None = None,
    ip_address: str | None = None,
    warehouse_id: UUID | None = None,
    payments: list[PaymentEntry] | None = None,
    discount_type: str | None = None,
    discount_value: Decimal | None = None,
) -> dict:
    """Process a multi-item POS sale with 15% Saudi VAT (prices are VAT-inclusive).

    Creates ONE journal entry for the entire cart:
        DEBIT  Cash (1000)              grand_total       (cash coming in)
        CREDIT Sales Revenue (4000)     total_net_revenue  (revenue ex-VAT)
        CREDIT VAT Payable (2200)       total_vat          (VAT liability)
        — per line item —
        DEBIT  COGS (5000)              item_cost          (expense)
        CREDIT Inventory (1100)         item_cost          (inventory out)
    """
    if not items:
        raise ValueError("Cart must contain at least one item")

    # ── Load & validate all products up-front ────────────────────────────
    line_details: list[dict] = []
    for item in items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise ValueError(f"Product {item.product_id} not found")

        # Warehouse-aware stock check
        if warehouse_id:
            ws = (
                db.query(WarehouseStock)
                .filter(
                    WarehouseStock.warehouse_id == warehouse_id,
                    WarehouseStock.product_id == item.product_id,
                )
                .first()
            )
            available = ws.quantity if ws else 0
            if available < item.quantity:
                raise ValueError(
                    f"Insufficient stock for '{product.name}' at warehouse: "
                    f"{available} available, {item.quantity} requested"
                )
        else:
            if product.current_stock < item.quantity:
                raise ValueError(
                    f"Insufficient stock for '{product.name}': "
                    f"{product.current_stock} available, {item.quantity} requested"
                )

        line_total = (Decimal(str(product.unit_price)) * item.quantity).quantize(Q, rounding=ROUND_HALF_UP)
        line_cost = (Decimal(str(product.cost_price)) * item.quantity).quantize(Q, rounding=ROUND_HALF_UP)

        line_details.append({
            "product": product,
            "quantity": item.quantity,
            "line_total": line_total,
            "line_cost": line_cost,
            "unit_price": Decimal(str(product.unit_price)),
        })

    # ── Cart-wide totals ─────────────────────────────────────────────────
    grand_total = sum(ld["line_total"] for ld in line_details)
    total_cost = sum(ld["line_cost"] for ld in line_details)

    # ── Apply discount ────────────────────────────────────────────────
    original_total = grand_total
    discount_amount = ZERO

    if discount_type and discount_value:
        if discount_type == "PERCENTAGE":
            discount_amount = (grand_total * discount_value / Decimal("100")).quantize(Q, rounding=ROUND_HALF_UP)
        elif discount_type == "FIXED_AMOUNT":
            discount_amount = discount_value.quantize(Q, rounding=ROUND_HALF_UP)

        if discount_amount >= grand_total:
            raise ValueError("Discount cannot equal or exceed the sale total")

        grand_total = grand_total - discount_amount

    total_vat = (grand_total * VAT_RATE / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)
    total_net = grand_total - total_vat

    # ── Load accounts ────────────────────────────────────────────────────
    sales_account = _get_account(db, SALES_ACCOUNT_CODE)
    vat_account = _get_account(db, VAT_PAYABLE_ACCOUNT_CODE)
    cogs_account = _get_account(db, COGS_ACCOUNT_CODE)
    inventory_account = _get_account(db, INVENTORY_ACCOUNT_CODE)

    # ── Invoice number ───────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    pos_count = (
        db.query(JournalEntry)
        .filter(JournalEntry.reference.like("INV-%"))
        .count()
    )
    invoice_number = generate_invoice_number(pos_count + 1, now.year)

    # ── ONE journal entry header ─────────────────────────────────────────
    item_count = len(line_details)
    description = (
        f"POS Sale: {line_details[0]['quantity']}x {line_details[0]['product'].name}"
        if item_count == 1
        else f"POS Sale: {item_count} items"
    )
    journal = JournalEntry(
        entry_date=now,
        description=description,
        reference=invoice_number,
        created_by=user_id,
    )
    db.add(journal)
    db.flush()

    # ── Resolve payment methods ────────────────────────────────────────
    if payments is None or len(payments) == 0:
        resolved_payments = [{"method": "CASH", "amount": grand_total}]
    else:
        resolved_payments = [
            {"method": p.method.value, "amount": p.amount.quantize(Q, rounding=ROUND_HALF_UP)}
            for p in payments
        ]
    payment_sum = sum(p["amount"] for p in resolved_payments)
    if payment_sum != grand_total:
        raise ValueError(
            f"Payment total ({payment_sum}) does not match sale total ({grand_total})"
        )

    # ── Revenue splits (one set for the whole cart) ──────────────────────
    # Debit split(s) per payment method
    payment_out: list[dict[str, str]] = []
    for pay in resolved_payments:
        pay_account = _get_account(db, PAYMENT_METHOD_ACCOUNT_MAP[pay["method"]])
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=pay_account.id,
            debit_amount=pay["amount"],
            credit_amount=ZERO,
        ))
        db.add(SalePayment(
            journal_entry_id=journal.id,
            payment_method=PaymentMethod(pay["method"]),
            account_id=pay_account.id,
            amount=pay["amount"],
        ))
        payment_out.append({"method": pay["method"], "amount": str(pay["amount"])})

    if discount_amount > ZERO:
        # Discount accounting: credit Sales at ORIGINAL net, debit Sales Discounts
        original_vat = (original_total * VAT_RATE / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)
        original_net = original_total - original_vat
        discount_net = original_net - total_net  # discount ex-VAT

        discount_account = _get_account(db, DISCOUNT_ACCOUNT_CODE)
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=discount_account.id,
            debit_amount=discount_net,
            credit_amount=ZERO,
        ))
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=sales_account.id,
            debit_amount=ZERO,
            credit_amount=original_net,
        ))
    else:
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=sales_account.id,
            debit_amount=ZERO,
            credit_amount=total_net,
        ))

    db.add(TransactionSplit(
        journal_entry_id=journal.id,
        account_id=vat_account.id,
        debit_amount=ZERO,
        credit_amount=total_vat,
    ))

    # ── Per-item: COGS/Inventory splits + stock deduction + Sale record ──
    invoice_items: list[dict] = []
    for ld in line_details:
        product: Product = ld["product"]
        line_cost: Decimal = ld["line_cost"]

        # COGS debit
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=cogs_account.id,
            debit_amount=line_cost,
            credit_amount=ZERO,
        ))
        # Inventory credit
        db.add(TransactionSplit(
            journal_entry_id=journal.id,
            account_id=inventory_account.id,
            debit_amount=ZERO,
            credit_amount=line_cost,
        ))

        # Deduct stock
        product.current_stock -= ld["quantity"]
        if warehouse_id:
            ws = (
                db.query(WarehouseStock)
                .filter(
                    WarehouseStock.warehouse_id == warehouse_id,
                    WarehouseStock.product_id == product.id,
                )
                .first()
            )
            if ws:
                ws.quantity -= ld["quantity"]

        # Sale record
        db.add(Sale(
            customer_id=customer_id,
            journal_entry_id=journal.id,
            product_id=product.id,
            quantity=ld["quantity"],
            total_amount=ld["line_total"],
        ))

        invoice_items.append({
            "product": product.name,
            "quantity": ld["quantity"],
            "unit_price": str(ld["unit_price"]),
            "line_total": str(ld["line_total"]),
        })

    # ── Store SaleDiscount record ────────────────────────────────────────
    if discount_amount > ZERO:
        db.add(SaleDiscount(
            journal_entry_id=journal.id,
            discount_type=DiscountType(discount_type),
            discount_value=discount_value,
            discount_amount=discount_amount,
        ))

    # ── ZATCA E-Invoice ────────────────────────────────────────────────────
    try:
        from backend.app.services.zatca.einvoice_service import (
            create_einvoice_for_sale,
            submit_einvoice_to_zatca,
        )

        customer_obj = None
        if customer_id:
            customer_obj = db.query(Customer).filter(Customer.id == customer_id).first()
        einvoice = create_einvoice_for_sale(
            db,
            journal_entry_id=journal.id,
            invoice_number=invoice_number,
            customer=customer_obj,
            line_details=line_details,
            payments=resolved_payments,
            total_net=total_net,
            total_vat=total_vat,
            grand_total=grand_total,
            discount_amount=discount_amount,
            now=now,
        )
        qr_code = einvoice.qr_code

        # Submit to ZATCA (non-blocking for sale — errors logged, not raised)
        try:
            submit_einvoice_to_zatca(db, einvoice)
        except Exception:
            pass  # Sale proceeds; invoice stays PENDING for retry
    except Exception:
        # Fallback to Phase 1 QR if Organization not configured
        qr_code = generate_zatca_qr(
            seller_name=SELLER_NAME,
            vat_number=VAT_REGISTRATION_NUMBER,
            timestamp=now,
            total_amount=str(grand_total),
            vat_amount=str(total_vat),
        )

    # ── Update customer totals ───────────────────────────────────────────
    if customer_id:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer:
            customer.total_spent = Decimal(str(customer.total_spent)) + grand_total
            customer.last_purchase_at = now

    # ── Audit log ────────────────────────────────────────────────────────
    log_action(
        db,
        user_id=user_id,
        action="SALE_COMPLETED",
        resource_type="sales",
        resource_id=invoice_number,
        ip_address=ip_address,
        changes={
            "invoice_number": invoice_number,
            "item_count": item_count,
            "total_collected": str(grand_total),
            "net_revenue": str(total_net),
            "vat_amount": str(total_vat),
            "total_cost": str(total_cost),
            "journal_entry_id": str(journal.id),
            "customer_id": str(customer_id) if customer_id else None,
            "payments": payment_out,
            "discount_type": discount_type,
            "discount_value": str(discount_value) if discount_value else None,
            "discount_amount": str(discount_amount),
        },
    )

    db.commit()

    return {
        "invoice_number": invoice_number,
        "timestamp": now.isoformat(timespec="seconds"),
        "journal_entry_id": str(journal.id),
        "items": invoice_items,
        "total_collected": str(grand_total),
        "net_revenue": str(total_net),
        "vat_amount": str(total_vat),
        "qr_code": qr_code,
        "payments": payment_out,
        "discount_amount": str(discount_amount),
        "original_total": str(original_total) if discount_amount > ZERO else "",
    }


# ─── Shift Management ──────────────────────────────────────────────────────


def _compute_shift_sales(db: Session, user_id: UUID, opened_at: datetime) -> Decimal:
    """Sum of cash collected from POS sales by this user since opened_at.

    Only counts debits on Cash account (1000). Card/Bank Transfer payments
    debit account 1200 and are automatically excluded.
    """
    cash_account = db.query(Account).filter(Account.code == CASH_ACCOUNT_CODE).first()
    if not cash_account:
        return Decimal("0")
    result = (
        db.query(sa_func.coalesce(sa_func.sum(TransactionSplit.debit_amount), Decimal("0")))
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .filter(
            JournalEntry.created_by == user_id,
            JournalEntry.created_at >= opened_at,
            JournalEntry.reference.like("INV-%"),
            TransactionSplit.account_id == cash_account.id,
        )
        .scalar()
    )
    return result or Decimal("0")


def _shift_to_out(db: Session, shift: Shift) -> ShiftOut:
    user = db.query(User).filter(User.id == shift.user_id).first()
    register = db.query(Register).filter(Register.id == shift.register_id).first()
    total_sales = _compute_shift_sales(db, shift.user_id, shift.opened_at)
    return ShiftOut(
        id=shift.id,
        register_id=shift.register_id,
        register_name=register.name if register else "Unknown",
        user_id=shift.user_id,
        username=user.username if user else "unknown",
        status=shift.status.value,
        opened_at=shift.opened_at.isoformat(),
        closed_at=shift.closed_at.isoformat() if shift.closed_at else None,
        opening_cash=str(shift.opening_cash),
        closing_cash_reported=str(shift.closing_cash_reported) if shift.closing_cash_reported is not None else None,
        expected_cash=str(shift.expected_cash) if shift.expected_cash is not None else None,
        discrepancy=str(shift.discrepancy) if shift.discrepancy is not None else None,
        total_sales=str(total_sales),
        notes=shift.notes,
    )


def get_active_shift(db: Session, user_id: UUID) -> ShiftOut | None:
    """Return the user's currently open shift, or None."""
    shift = (
        db.query(Shift)
        .filter(Shift.user_id == user_id, Shift.status == ShiftStatus.OPEN)
        .first()
    )
    if not shift:
        return None
    return _shift_to_out(db, shift)


def open_shift(
    db: Session,
    user_id: UUID,
    register_id: UUID,
    opening_cash: Decimal,
    ip_address: str | None = None,
) -> ShiftOut:
    """Open a new cash register shift."""
    # Check user doesn't already have an open shift
    existing = (
        db.query(Shift)
        .filter(Shift.user_id == user_id, Shift.status == ShiftStatus.OPEN)
        .first()
    )
    if existing:
        raise ValueError("You already have an open shift. Close it before opening a new one.")

    # Verify register exists
    register = db.query(Register).filter(Register.id == register_id).first()
    if not register:
        raise ValueError("Register not found")

    shift = Shift(
        register_id=register_id,
        user_id=user_id,
        status=ShiftStatus.OPEN,
        opening_cash=opening_cash,
    )
    db.add(shift)
    db.flush()

    log_action(
        db,
        user_id=user_id,
        action="SHIFT_OPENED",
        resource_type="shifts",
        resource_id=str(shift.id),
        ip_address=ip_address,
        changes={
            "register": register.name,
            "opening_cash": str(opening_cash),
        },
    )

    db.commit()
    db.refresh(shift)
    return _shift_to_out(db, shift)


def close_shift(
    db: Session,
    shift_id: UUID,
    user_id: UUID,
    closing_cash_reported: Decimal,
    notes: str | None = None,
    ip_address: str | None = None,
) -> ShiftOut:
    """Close a shift, compute expected cash, record discrepancy journal entry."""
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise ValueError("Shift not found")
    if shift.user_id != user_id:
        raise ValueError("You can only close your own shift")
    if shift.status != ShiftStatus.OPEN:
        raise ValueError("Shift is already closed")

    now = datetime.now(timezone.utc)

    # Compute expected cash = opening + sales during shift
    total_sales = _compute_shift_sales(db, user_id, shift.opened_at)
    expected = shift.opening_cash + total_sales
    disc = closing_cash_reported - expected

    shift.status = ShiftStatus.CLOSED
    shift.closed_at = now
    shift.closing_cash_reported = closing_cash_reported
    shift.expected_cash = expected
    shift.discrepancy = disc
    shift.notes = notes

    # ── Journal entry for discrepancy if non-zero ─────────────────────────
    if disc != Decimal("0"):
        cash_account = _get_account(db, CASH_ACCOUNT_CODE)

        if disc < 0:
            # Shortage: DEBIT Cash Shortage Expense / CREDIT Cash
            contra = _get_account(db, CASH_SHORTAGE_ACCOUNT_CODE)
            abs_disc = abs(disc)
            journal = JournalEntry(
                entry_date=now,
                description=f"Cash shortage on shift close: {abs_disc}",
                reference=f"SHIFT-SHORT-{str(shift.id)[:8]}",
                created_by=user_id,
            )
            db.add(journal)
            db.flush()
            db.add(TransactionSplit(
                journal_entry_id=journal.id,
                account_id=contra.id,
                debit_amount=abs_disc,
                credit_amount=Decimal("0"),
            ))
            db.add(TransactionSplit(
                journal_entry_id=journal.id,
                account_id=cash_account.id,
                debit_amount=Decimal("0"),
                credit_amount=abs_disc,
            ))
        else:
            # Overage: DEBIT Cash / CREDIT Other Income
            contra = _get_account(db, OTHER_INCOME_ACCOUNT_CODE)
            journal = JournalEntry(
                entry_date=now,
                description=f"Cash overage on shift close: {disc}",
                reference=f"SHIFT-OVER-{str(shift.id)[:8]}",
                created_by=user_id,
            )
            db.add(journal)
            db.flush()
            db.add(TransactionSplit(
                journal_entry_id=journal.id,
                account_id=cash_account.id,
                debit_amount=disc,
                credit_amount=Decimal("0"),
            ))
            db.add(TransactionSplit(
                journal_entry_id=journal.id,
                account_id=contra.id,
                debit_amount=Decimal("0"),
                credit_amount=disc,
            ))

    log_action(
        db,
        user_id=user_id,
        action="SHIFT_CLOSED",
        resource_type="shifts",
        resource_id=str(shift.id),
        ip_address=ip_address,
        changes={
            "closing_cash_reported": str(closing_cash_reported),
            "expected_cash": str(expected),
            "discrepancy": str(disc),
            "total_sales": str(total_sales),
        },
    )

    db.commit()
    db.refresh(shift)
    return _shift_to_out(db, shift)


def list_shifts(db: Session) -> list[ShiftOut]:
    """Return all shifts, most recent first."""
    shifts = (
        db.query(Shift)
        .order_by(Shift.opened_at.desc())
        .limit(50)
        .all()
    )
    return [_shift_to_out(db, s) for s in shifts]
