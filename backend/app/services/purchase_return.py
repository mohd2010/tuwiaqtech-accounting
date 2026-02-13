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
from backend.app.models.inventory import Product
from backend.app.models.returns import ItemCondition
from backend.app.models.supplier import (
    POStatus,
    PRStatus,
    PurchaseOrder,
    PurchaseReturn,
    PurchaseReturnItem,
)
from backend.app.services.audit import log_action

# ── Account codes ────────────────────────────────────────────────────────────
AP_ACCOUNT_CODE = "2100"
INVENTORY_ACCOUNT_CODE = "1100"
SHRINKAGE_ACCOUNT_CODE = "5200"

Q = Decimal("0.0001")
ZERO = Decimal("0")


def _get_account(db: Session, code: str) -> Account:
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        raise ValueError(f"Account {code} not found in chart of accounts")
    return account


# ─── PO Lookup ───────────────────────────────────────────────────────────────


def lookup_po(db: Session, po_id: UUID) -> dict:
    """Look up a received PO and return returnable item quantities."""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise ValueError("Purchase order not found")
    if po.status != POStatus.RECEIVED:
        raise ValueError(f"Cannot return items from PO with status {po.status.value}")

    # Calculate already-returned quantities from ISSUED purchase returns
    already_returned: dict[UUID, int] = {}
    existing_prs = (
        db.query(PurchaseReturn)
        .filter(
            PurchaseReturn.po_id == po.id,
            PurchaseReturn.status == PRStatus.ISSUED,
        )
        .all()
    )
    for pr in existing_prs:
        for item in pr.items:
            already_returned[item.product_id] = (
                already_returned.get(item.product_id, 0) + item.quantity
            )

    # Build response items
    items: list[dict] = []
    for po_item in po.items:
        product = db.query(Product).filter(Product.id == po_item.product_id).first()
        if not product:
            continue

        qty_returned = already_returned.get(po_item.product_id, 0)
        returnable = po_item.quantity - qty_returned

        items.append({
            "product_id": str(po_item.product_id),
            "product_name": product.name,
            "sku": product.sku,
            "quantity_ordered": po_item.quantity,
            "quantity_returned": qty_returned,
            "returnable_quantity": returnable,
            "unit_cost": str(po_item.unit_cost),
        })

    supplier = po.supplier

    return {
        "po_id": str(po.id),
        "supplier_name": supplier.name,
        "received_at": po.created_at.isoformat(timespec="seconds"),
        "items": items,
        "total_amount": str(po.total_amount),
    }


# ─── Process Purchase Return ────────────────────────────────────────────────


def process_purchase_return(
    db: Session,
    po_id: UUID,
    items: list[dict],
    reason: str,
    user_id: UUID,
    ip_address: str | None = None,
) -> dict:
    """Process a purchase return (debit note) against a received PO.

    Creates a reversal journal entry, purchase return records, and decreases stock.
    """
    # ── Find and validate PO ─────────────────────────────────────────────
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise ValueError("Purchase order not found")
    if po.status != POStatus.RECEIVED:
        raise ValueError(f"Cannot return items from PO with status {po.status.value}")

    # Build map: product_id → PurchaseOrderItem
    po_item_map = {item.product_id: item for item in po.items}

    # Calculate already-returned quantities
    already_returned: dict[UUID, int] = {}
    existing_prs = (
        db.query(PurchaseReturn)
        .filter(
            PurchaseReturn.po_id == po.id,
            PurchaseReturn.status == PRStatus.ISSUED,
        )
        .all()
    )
    for pr in existing_prs:
        for pr_item in pr.items:
            already_returned[pr_item.product_id] = (
                already_returned.get(pr_item.product_id, 0) + pr_item.quantity
            )

    # ── Validate return items ────────────────────────────────────────────
    line_details: list[dict] = []
    for item in items:
        product_id = UUID(item["product_id"]) if isinstance(item["product_id"], str) else item["product_id"]
        quantity = item["quantity"]
        condition = item["condition"]

        if product_id not in po_item_map:
            raise ValueError(f"Product {product_id} was not in the purchase order")

        po_item = po_item_map[product_id]
        prev_returned = already_returned.get(product_id, 0)
        returnable = po_item.quantity - prev_returned

        if quantity > returnable:
            raise ValueError(
                f"Cannot return {quantity} of product {product_id}: "
                f"only {returnable} returnable"
            )

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        unit_cost = Decimal(str(po_item.unit_cost))
        line_total = (unit_cost * quantity).quantize(Q, rounding=ROUND_HALF_UP)

        line_details.append({
            "product": product,
            "product_id": product_id,
            "quantity": quantity,
            "condition": condition,
            "unit_cost": unit_cost,
            "line_total": line_total,
        })

    # ── Calculate total ──────────────────────────────────────────────────
    total_amount = sum(ld["line_total"] for ld in line_details)

    # ── Load accounts ────────────────────────────────────────────────────
    ap_account = _get_account(db, AP_ACCOUNT_CODE)
    inventory_account = _get_account(db, INVENTORY_ACCOUNT_CODE)
    shrinkage_account = _get_account(db, SHRINKAGE_ACCOUNT_CODE)

    # ── Generate return number ───────────────────────────────────────────
    now = datetime.now(timezone.utc)
    pr_count = (
        db.query(sa_func.count(PurchaseReturn.id))
        .filter(PurchaseReturn.return_number.like("PR-%"))
        .scalar()
    ) or 0
    return_number = f"PR-{now.year}-{pr_count + 1:04d}"

    # ── Create reversal journal entry ────────────────────────────────────
    description = f"Purchase Return: {return_number} against PO {str(po.id)[:8].upper()}"
    journal = JournalEntry(
        entry_date=now,
        description=description,
        reference=return_number,
        created_by=user_id,
    )
    db.add(journal)
    db.flush()

    # DEBIT AP (2100) — reduce what we owe supplier
    db.add(TransactionSplit(
        journal_entry_id=journal.id,
        account_id=ap_account.id,
        debit_amount=total_amount,
        credit_amount=ZERO,
    ))

    # ── Per-item splits + stock adjustments ──────────────────────────────
    pr_items_out: list[dict] = []
    pr_items: list[PurchaseReturnItem] = []

    for ld in line_details:
        product: Product = ld["product"]
        line_total: Decimal = ld["line_total"]
        condition: str = ld["condition"]

        if condition == "RESALABLE":
            # CREDIT Inventory (1100) — reduce inventory asset
            db.add(TransactionSplit(
                journal_entry_id=journal.id,
                account_id=inventory_account.id,
                debit_amount=ZERO,
                credit_amount=line_total,
            ))
        else:
            # CREDIT Shrinkage (5200) — expense the loss
            db.add(TransactionSplit(
                journal_entry_id=journal.id,
                account_id=shrinkage_account.id,
                debit_amount=ZERO,
                credit_amount=line_total,
            ))

        # Decrease stock for ALL returned items (leaving our warehouse)
        product.current_stock -= ld["quantity"]

        pr_item = PurchaseReturnItem(
            product_id=ld["product_id"],
            quantity=ld["quantity"],
            unit_cost=ld["unit_cost"],
            condition=ItemCondition(condition),
        )
        pr_items.append(pr_item)

        pr_items_out.append({
            "product_name": product.name,
            "quantity": ld["quantity"],
            "condition": condition,
            "unit_cost": str(ld["unit_cost"]),
            "line_total": str(ld["line_total"]),
        })

    # ── Create PurchaseReturn record ─────────────────────────────────────
    purchase_return = PurchaseReturn(
        po_id=po.id,
        return_number=return_number,
        reason=reason,
        status=PRStatus.ISSUED,
        total_amount=total_amount,
        journal_entry_id=journal.id,
        created_by=user_id,
    )
    db.add(purchase_return)
    db.flush()

    for pr_item in pr_items:
        pr_item.purchase_return_id = purchase_return.id
        db.add(pr_item)

    # ── Audit log ────────────────────────────────────────────────────────
    log_action(
        db,
        user_id=user_id,
        action="PURCHASE_RETURN_PROCESSED",
        resource_type="purchase_returns",
        resource_id=return_number,
        ip_address=ip_address,
        changes={
            "return_number": return_number,
            "po_id": str(po.id),
            "reason": reason,
            "total_amount": str(total_amount),
            "journal_entry_id": str(journal.id),
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
        "return_number": return_number,
        "po_id": str(po.id),
        "supplier_name": po.supplier.name,
        "timestamp": now.isoformat(timespec="seconds"),
        "reason": reason,
        "items": pr_items_out,
        "total_amount": str(total_amount),
        "journal_entry_id": str(journal.id),
    }
