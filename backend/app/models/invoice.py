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
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class InvoiceStatus(str, enum.Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    PAID = "PAID"


class CreditInvoice(Base):
    __tablename__ = "credit_invoices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False
    )
    invoice_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    invoice_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False, default=Decimal("0")
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), nullable=False, default=InvoiceStatus.OPEN
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    customer: Mapped["Customer"] = relationship()  # noqa: F821
    journal_entry: Mapped["JournalEntry"] = relationship()  # noqa: F821
    payments: Mapped[list[InvoicePayment]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_credit_invoices_customer", "customer_id"),
        Index("ix_credit_invoices_status", "status"),
        Index("ix_credit_invoices_due_date", "due_date"),
    )


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credit_invoices.id"), nullable=False
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    invoice: Mapped[CreditInvoice] = relationship(back_populates="payments")
    journal_entry: Mapped["JournalEntry"] = relationship()  # noqa: F821

    __table_args__ = (
        Index("ix_invoice_payments_invoice", "invoice_id"),
    )
