from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    JournalEntry,
    TransactionSplit,
    User,
)
from backend.app.models.inventory import AdjustmentType, InventoryTransaction, Product
from backend.app.schemas.inventory import StockAdjustmentOut
from backend.app.services.audit import log_action

INVENTORY_ACCOUNT_CODE = "1100"
SHRINKAGE_ACCOUNT_CODE = "5200"
OTHER_INCOME_ACCOUNT_CODE = "4200"


def add_stock_with_transaction(
    db: Session,
    product_id: UUID,
    quantity: int,
    total_cost: Decimal,
    payment_account_id: UUID,
    user_id: UUID,
    ip_address: str | None = None,
) -> Product:
    """Add stock to a product and record the matching journal entry.

    Accounting effect:
        DEBIT  Inventory (1100)          total_cost
        CREDIT payment_account_id        total_cost
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ValueError("Product not found")

    inventory_account = (
        db.query(Account).filter(Account.code == INVENTORY_ACCOUNT_CODE).first()
    )
    if not inventory_account:
        raise ValueError("Inventory account (1100) not found in chart of accounts")

    payment_account = (
        db.query(Account).filter(Account.id == payment_account_id).first()
    )
    if not payment_account:
        raise ValueError("Payment account not found")

    # ── Journal entry ─────────────────────────────────────────────────────
    journal = JournalEntry(
        entry_date=datetime.now(timezone.utc),
        description=f"Stock-in: {quantity}x {product.name}",
        reference=f"STOCK-IN-{product.sku}",
        created_by=user_id,
    )
    db.add(journal)
    db.flush()

    db.add(
        TransactionSplit(
            journal_entry_id=journal.id,
            account_id=inventory_account.id,
            debit_amount=total_cost,
            credit_amount=Decimal("0"),
        )
    )
    db.add(
        TransactionSplit(
            journal_entry_id=journal.id,
            account_id=payment_account_id,
            debit_amount=Decimal("0"),
            credit_amount=total_cost,
        )
    )

    # ── Update stock ──────────────────────────────────────────────────────
    product.current_stock += quantity

    # ── Audit log ─────────────────────────────────────────────────────────
    log_action(
        db,
        user_id=user_id,
        action="STOCK_ADJUSTMENT",
        resource_type="products",
        resource_id=str(product.id),
        ip_address=ip_address,
        changes={
            "product": product.name,
            "quantity_added": quantity,
            "total_cost": str(total_cost),
            "payment_account": str(payment_account_id),
            "journal_entry_id": str(journal.id),
        },
    )

    db.commit()
    db.refresh(product)
    return product


# ─── Stock Adjustments ──────────────────────────────────────────────────────


def _get_account_by_code(db: Session, code: str) -> Account:
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        raise ValueError(f"Account {code} not found in chart of accounts")
    return account


def create_stock_adjustment(
    db: Session,
    user_id: UUID,
    product_id: UUID,
    quantity: int,
    adjustment_type: str,
    notes: str | None = None,
    ip_address: str | None = None,
) -> StockAdjustmentOut:
    """Create a stock adjustment with matching journal entry.

    Negative quantity = loss (damage/theft):
        DEBIT  Inventory Shrinkage (5200)
        CREDIT Inventory (1100)
    Positive quantity = gain (found items / count error):
        DEBIT  Inventory (1100)
        CREDIT Other Income (4200)
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ValueError("Product not found")

    # Validate stock won't go negative
    new_stock = product.current_stock + quantity
    if new_stock < 0:
        raise ValueError(
            f"Insufficient stock: current {product.current_stock}, "
            f"adjustment {quantity} would result in {new_stock}"
        )

    inventory_account = _get_account_by_code(db, INVENTORY_ACCOUNT_CODE)
    abs_amount = Decimal(str(abs(quantity))) * product.cost_price

    if abs_amount <= 0:
        raise ValueError("Adjustment amount must be greater than zero")

    adj_type = AdjustmentType(adjustment_type)

    # ── Journal entry ─────────────────────────────────────────────────────
    is_loss = quantity < 0

    if is_loss:
        contra_account = _get_account_by_code(db, SHRINKAGE_ACCOUNT_CODE)
        description = f"Inventory {adj_type.value.lower()}: {abs(quantity)}x {product.name}"
        reference = f"ADJ-{adj_type.value}-{product.sku}"
        debit_account_id = contra_account.id
        credit_account_id = inventory_account.id
    else:
        contra_account = _get_account_by_code(db, OTHER_INCOME_ACCOUNT_CODE)
        description = f"Inventory correction: +{quantity}x {product.name}"
        reference = f"ADJ-{adj_type.value}-{product.sku}"
        debit_account_id = inventory_account.id
        credit_account_id = contra_account.id

    journal = JournalEntry(
        entry_date=datetime.now(timezone.utc),
        description=description,
        reference=reference,
        created_by=user_id,
    )
    db.add(journal)
    db.flush()

    db.add(
        TransactionSplit(
            journal_entry_id=journal.id,
            account_id=debit_account_id,
            debit_amount=abs_amount,
            credit_amount=Decimal("0"),
        )
    )
    db.add(
        TransactionSplit(
            journal_entry_id=journal.id,
            account_id=credit_account_id,
            debit_amount=Decimal("0"),
            credit_amount=abs_amount,
        )
    )

    # ── Update stock ──────────────────────────────────────────────────────
    product.current_stock = new_stock

    # ── Record transaction ────────────────────────────────────────────────
    txn = InventoryTransaction(
        product_id=product.id,
        adjustment_type=adj_type,
        quantity=quantity,
        notes=notes,
        journal_entry_id=journal.id,
        created_by=user_id,
    )
    db.add(txn)

    # ── Audit log ─────────────────────────────────────────────────────────
    log_action(
        db,
        user_id=user_id,
        action="STOCK_ADJUSTMENT",
        resource_type="inventory_transactions",
        resource_id=str(txn.id),
        ip_address=ip_address,
        changes={
            "product": product.name,
            "adjustment_type": adj_type.value,
            "quantity": quantity,
            "amount": str(abs_amount),
            "journal_entry_id": str(journal.id),
        },
    )

    db.commit()
    db.refresh(txn)

    user = db.query(User).filter(User.id == user_id).first()

    return StockAdjustmentOut(
        id=txn.id,
        product_name=product.name,
        product_sku=product.sku,
        adjustment_type=txn.adjustment_type.value,
        quantity=txn.quantity,
        notes=txn.notes,
        created_by_username=user.username if user else "unknown",
        created_at=txn.created_at.isoformat(),
    )


def list_adjustments(db: Session) -> list[StockAdjustmentOut]:
    """Return all stock adjustments, most recent first."""
    rows = (
        db.query(InventoryTransaction, Product.name, Product.sku, User.username)
        .join(Product, InventoryTransaction.product_id == Product.id)
        .join(User, InventoryTransaction.created_by == User.id)
        .order_by(InventoryTransaction.created_at.desc())
        .all()
    )
    return [
        StockAdjustmentOut(
            id=txn.id,
            product_name=prod_name,
            product_sku=prod_sku,
            adjustment_type=txn.adjustment_type.value,
            quantity=txn.quantity,
            notes=txn.notes,
            created_by_username=username,
            created_at=txn.created_at.isoformat(),
        )
        for txn, prod_name, prod_sku, username in rows
    ]
