from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class AdjustmentType(str, enum.Enum):
    DAMAGE = "DAMAGE"
    THEFT = "THEFT"
    COUNT_ERROR = "COUNT_ERROR"
    PROMOTION = "PROMOTION"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(Base):
    """Inventory product.

    NOTE: `current_stock` should NEVER be set directly on creation when > 0.
    Initial stock must be recorded through a Journal Entry that debits the
    Inventory account and credits Owner's Equity. This will be implemented
    in an inventory service that wraps product creation + journal entry in
    a single transaction. For now, current_stock defaults to 0.
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    cost_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    category: Mapped[Category] = relationship(back_populates="products")

    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_product_unit_price_non_negative"),
        CheckConstraint("cost_price >= 0", name="ck_product_cost_price_non_negative"),
        CheckConstraint("current_stock >= 0", name="ck_product_stock_non_negative"),
        Index("ix_products_sku", "sku"),
        Index("ix_products_category", "category_id"),
    )


class InventoryTransaction(Base):
    """Records every stock adjustment (damage, theft, count error, promotion)."""

    __tablename__ = "inventory_transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    adjustment_type: Mapped[AdjustmentType] = mapped_column(
        Enum(AdjustmentType), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    product: Mapped[Product] = relationship()

    __table_args__ = (
        Index("ix_inv_txn_product", "product_id"),
        Index("ix_inv_txn_created_at", "created_at"),
    )


# ─── Multi-Warehouse ──────────────────────────────────────────────────────────


class TransferStatus(str, enum.Enum):
    PENDING = "PENDING"
    SHIPPED = "SHIPPED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    stock_entries: Mapped[list[WarehouseStock]] = relationship(back_populates="warehouse")


class WarehouseStock(Base):
    __tablename__ = "warehouse_stock"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("warehouses.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    warehouse: Mapped[Warehouse] = relationship(back_populates="stock_entries")
    product: Mapped[Product] = relationship()

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_warehouse_stock_qty_non_negative"),
        UniqueConstraint("warehouse_id", "product_id", name="uq_warehouse_product"),
        Index("ix_ws_warehouse", "warehouse_id"),
        Index("ix_ws_product", "product_id"),
    )


class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    from_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("warehouses.id"), nullable=False
    )
    to_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("warehouses.id"), nullable=False
    )
    status: Mapped[TransferStatus] = mapped_column(
        Enum(TransferStatus), nullable=False, default=TransferStatus.PENDING
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    from_warehouse: Mapped[Warehouse] = relationship(foreign_keys=[from_warehouse_id])
    to_warehouse: Mapped[Warehouse] = relationship(foreign_keys=[to_warehouse_id])
    items: Mapped[list[StockTransferItem]] = relationship(back_populates="transfer")

    __table_args__ = (
        CheckConstraint(
            "from_warehouse_id != to_warehouse_id",
            name="ck_transfer_different_warehouses",
        ),
        Index("ix_transfers_status", "status"),
        Index("ix_transfers_created_at", "created_at"),
    )


class StockTransferItem(Base):
    __tablename__ = "stock_transfer_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    transfer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_transfers.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    transfer: Mapped[StockTransfer] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_transfer_item_qty_positive"),
    )
