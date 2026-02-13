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


# ─── Enums ────────────────────────────────────────────────────────────────────


class CreditNoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"


class ItemCondition(str, enum.Enum):
    RESALABLE = "RESALABLE"
    DAMAGED = "DAMAGED"


# ─── Credit Note (Header) ────────────────────────────────────────────────────


class CreditNote(Base):
    """A credit note issued against an original sale for returned items.

    Each credit note references the original sale journal entry and creates
    a new reversal journal entry. Credit notes are immutable once ISSUED —
    corrections require a new credit note.
    """

    __tablename__ = "credit_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    original_journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False
    )
    credit_note_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CreditNoteStatus] = mapped_column(
        Enum(CreditNoteStatus), nullable=False, default=CreditNoteStatus.DRAFT
    )
    total_refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    vat_refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    net_refund_amount: Mapped[Decimal] = mapped_column(
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

    original_journal_entry: Mapped["JournalEntry"] = relationship(  # noqa: F821
        foreign_keys=[original_journal_entry_id]
    )
    refund_journal_entry: Mapped["JournalEntry | None"] = relationship(  # noqa: F821
        foreign_keys=[journal_entry_id]
    )
    items: Mapped[list[CreditNoteItem]] = relationship(
        back_populates="credit_note", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_credit_notes_original_je", "original_journal_entry_id"),
        Index("ix_credit_notes_status", "status"),
        Index("ix_credit_notes_created_at", "created_at"),
    )


# ─── Credit Note Item (Line Item) ────────────────────────────────────────────


class CreditNoteItem(Base):
    """A single line item on a credit note, representing one returned product."""

    __tablename__ = "credit_note_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credit_notes.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[ItemCondition] = mapped_column(
        Enum(ItemCondition), nullable=False
    )
    unit_refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    line_refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )

    credit_note: Mapped[CreditNote] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()  # noqa: F821

    __table_args__ = (
        Index("ix_credit_note_items_cn", "credit_note_id"),
        Index("ix_credit_note_items_product", "product_id"),
    )
