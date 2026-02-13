from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
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


# ─── Enums ────────────────────────────────────────────────────────────────────


class QuoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CONVERTED = "CONVERTED"


# ─── Quote ────────────────────────────────────────────────────────────────────


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    quote_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_vat: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[QuoteStatus] = mapped_column(
        Enum(QuoteStatus), nullable=False, default=QuoteStatus.DRAFT
    )
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False, default=Decimal("0")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[list[QuoteItem]] = relationship(
        back_populates="quote", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_quotes_number", "quote_number"),
        Index("ix_quotes_status", "status"),
        Index("ix_quotes_created_at", "created_at"),
        Index("ix_quotes_created_by", "created_by"),
    )


# ─── Quote Item ───────────────────────────────────────────────────────────────


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quotes.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )

    quote: Mapped[Quote] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()  # noqa: F821

    __table_args__ = (
        Index("ix_quote_items_quote", "quote_id"),
        Index("ix_quote_items_product", "product_id"),
    )
