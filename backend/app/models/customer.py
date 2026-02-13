from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=4), nullable=True
    )
    payment_terms_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    total_spent: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False, default=Decimal("0")
    )
    last_purchase_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # ZATCA address fields (for B2B buyer info)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    building_number: Mapped[str | None] = mapped_column(String(4), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    district: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, default="SA")
    additional_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sales: Mapped[list[Sale]] = relationship(back_populates="customer")

    __table_args__ = (
        Index("ix_customers_name", "name"),
        Index("ix_customers_email", "email"),
        Index("ix_customers_phone", "phone"),
    )


class Sale(Base):
    """Links a POS transaction (journal entry) to a customer."""

    __tablename__ = "sales"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    customer: Mapped[Customer | None] = relationship(back_populates="sales")
    journal_entry: Mapped["JournalEntry"] = relationship()  # noqa: F821
    product: Mapped["Product"] = relationship()  # noqa: F821

    __table_args__ = (
        Index("ix_sales_customer", "customer_id"),
        Index("ix_sales_journal_entry", "journal_entry_id"),
        Index("ix_sales_created_at", "created_at"),
    )
