from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import (
    Account,
    AuditLog,
    JournalEntry,
    TransactionSplit,
    User,
)
from backend.app.models.inventory import Product
from backend.app.models.supplier import POStatus, PurchaseOrder, PurchaseOrderItem
from backend.app.schemas.supplier import PurchaseOrderCreate, PurchaseOrderOut

router = APIRouter()

INVENTORY_ACCOUNT_CODE = "1100"
AP_ACCOUNT_CODE = "2100"


def _get_account(db: Session, code: str) -> Account:
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        raise ValueError(f"Account {code} not found in chart of accounts")
    return account


@router.get("/", response_model=list[PurchaseOrderOut])
def list_purchase_orders(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("purchase:read")),
) -> list[PurchaseOrder]:
    return (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.items))
        .order_by(PurchaseOrder.created_at.desc())
        .all()
    )


@router.post("/", response_model=PurchaseOrderOut, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase:write")),
) -> PurchaseOrder:
    # Validate products exist
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(
                status_code=400,
                detail=f"Product {item.product_id} not found",
            )

    total = sum(item.unit_cost * item.quantity for item in payload.items)

    po = PurchaseOrder(
        supplier_id=payload.supplier_id,
        status=POStatus.PENDING,
        total_amount=total,
        created_by=current_user.id,
    )
    db.add(po)
    db.flush()

    for item in payload.items:
        db.add(PurchaseOrderItem(
            po_id=po.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_cost=item.unit_cost,
        ))

    db.commit()
    db.refresh(po)
    return po


@router.get("/{po_id}", response_model=PurchaseOrderOut)
def get_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("purchase:read")),
) -> PurchaseOrder:
    po = (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.items))
        .filter(PurchaseOrder.id == po_id)
        .first()
    )
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


@router.patch("/{po_id}/receive", response_model=PurchaseOrderOut)
def receive_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase:write")),
) -> PurchaseOrder:
    """Mark a PO as RECEIVED: increment stock and create journal entry."""
    po = (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.items))
        .filter(PurchaseOrder.id == po_id)
        .first()
    )
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status != POStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot receive PO with status {po.status.value}",
        )

    inventory_account = _get_account(db, INVENTORY_ACCOUNT_CODE)
    ap_account = _get_account(db, AP_ACCOUNT_CODE)

    # ── Increment stock for each item ────────────────────────────────────
    for item in po.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(
                status_code=400,
                detail=f"Product {item.product_id} not found",
            )
        product.current_stock += item.quantity

    # ── Journal entry: DEBIT Inventory, CREDIT Accounts Payable ──────────
    now = datetime.now(timezone.utc)
    journal = JournalEntry(
        entry_date=now,
        description=f"PO Received: {po.id}",
        reference=f"PO-{str(po.id)[:8].upper()}",
        created_by=current_user.id,
    )
    db.add(journal)
    db.flush()

    total = Decimal(str(po.total_amount))

    db.add(TransactionSplit(
        journal_entry_id=journal.id,
        account_id=inventory_account.id,
        debit_amount=total,
        credit_amount=Decimal("0"),
    ))
    db.add(TransactionSplit(
        journal_entry_id=journal.id,
        account_id=ap_account.id,
        debit_amount=Decimal("0"),
        credit_amount=total,
    ))

    # ── Update PO status ─────────────────────────────────────────────────
    po.status = POStatus.RECEIVED

    # ── Audit log ────────────────────────────────────────────────────────
    db.add(AuditLog(
        table_name="purchase_orders",
        record_id=str(po.id),
        action="PO_RECEIVED",
        changed_by=current_user.id,
        new_values={
            "total_amount": str(total),
            "journal_entry_id": str(journal.id),
            "items_count": len(po.items),
        },
    ))

    db.commit()
    db.refresh(po)
    return po


@router.patch("/{po_id}/cancel", response_model=PurchaseOrderOut)
def cancel_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase:write")),
) -> PurchaseOrder:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status != POStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel PO with status {po.status.value}",
        )
    po.status = POStatus.CANCELLED
    db.commit()
    db.refresh(po)
    return po
