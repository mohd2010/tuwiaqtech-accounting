from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"


class DiscountType(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class ShiftStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Register(Base):
    __tablename__ = "registers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("warehouses.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    shifts: Mapped[list[Shift]] = relationship(back_populates="register")
    warehouse = relationship("Warehouse")


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    register_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registers.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus), nullable=False, default=ShiftStatus.OPEN
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opening_cash: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False, default=Decimal("0")
    )
    closing_cash_reported: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=4), nullable=True
    )
    expected_cash: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=4), nullable=True
    )
    discrepancy: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=4), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    register: Mapped[Register] = relationship(back_populates="shifts")

    __table_args__ = (
        Index("ix_shifts_user", "user_id"),
        Index("ix_shifts_register", "register_id"),
        Index("ix_shifts_status", "status"),
        Index("ix_shifts_opened_at", "opened_at"),
    )


class SalePayment(Base):
    __tablename__ = "sale_payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_sale_payment_amount_positive"),
        Index("ix_sale_payments_journal", "journal_entry_id"),
        Index("ix_sale_payments_method", "payment_method"),
        Index("ix_sale_payments_account", "account_id"),
    )


class SaleDiscount(Base):
    __tablename__ = "sale_discounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False, unique=True
    )
    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType), nullable=False
    )
    discount_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("discount_value > 0", name="ck_sale_discount_value_positive"),
        CheckConstraint("discount_amount > 0", name="ck_sale_discount_amount_positive"),
        Index("ix_sale_discounts_journal", "journal_entry_id"),
    )
