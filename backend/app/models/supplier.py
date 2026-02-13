from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.models.returns import ItemCondition


class POStatus(str, enum.Enum):
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class PRStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(back_populates="supplier")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False
    )
    status: Mapped[POStatus] = mapped_column(
        Enum(POStatus), nullable=False, default=POStatus.PENDING
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False, default=Decimal("0")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    supplier: Mapped[Supplier] = relationship(back_populates="purchase_orders")
    items: Mapped[list[PurchaseOrderItem]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_po_supplier", "supplier_id"),
        Index("ix_po_status", "status"),
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    po_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")

    __table_args__ = (
        Index("ix_po_items_po", "po_id"),
        Index("ix_po_items_product", "product_id"),
    )


class PurchaseReturn(Base):
    __tablename__ = "purchase_returns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    po_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False
    )
    return_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PRStatus] = mapped_column(
        Enum(PRStatus), nullable=False, default=PRStatus.DRAFT
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    purchase_order: Mapped[PurchaseOrder] = relationship()
    items: Mapped[list[PurchaseReturnItem]] = relationship(
        back_populates="purchase_return", cascade="all, delete-orphan"
    )
    journal_entry: Mapped["JournalEntry | None"] = relationship()  # noqa: F821

    __table_args__ = (
        Index("ix_purchase_returns_po", "po_id"),
        Index("ix_purchase_returns_status", "status"),
        Index("ix_purchase_returns_created_at", "created_at"),
    )


class PurchaseReturnItem(Base):
    __tablename__ = "purchase_return_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    purchase_return_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_returns.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    condition: Mapped[ItemCondition] = mapped_column(
        Enum(ItemCondition, create_constraint=False), nullable=False
    )

    purchase_return: Mapped[PurchaseReturn] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()  # noqa: F821

    __table_args__ = (
        Index("ix_pr_items_pr", "purchase_return_id"),
        Index("ix_pr_items_product", "product_id"),
    )
