from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


class JournalEntry(Base):
    """Immutable journal entry header.

    Double-entry integrity (sum(debits) == sum(credits)) cannot be enforced
    purely at the DB column level because it spans child rows. Enforce this in
    the service layer (services/journal.py) inside the same DB transaction
    BEFORE committing. A CHECK constraint on the splits table guarantees each
    line is either a debit or credit, never both.
    """

    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entry_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    created_by_user: Mapped["User"] = relationship(back_populates="journal_entries")  # noqa: F821
    splits: Mapped[list[TransactionSplit]] = relationship(
        back_populates="journal_entry", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_journal_entries_date", "entry_date"),
    )


class TransactionSplit(Base):
    """A single debit or credit line within a journal entry.

    Exactly one of debit_amount / credit_amount must be > 0; the other must
    be 0. This is enforced by a CHECK constraint at the DB level.
    """

    __tablename__ = "transaction_splits"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id"), nullable=False
    )
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False, default=Decimal("0")
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False, default=Decimal("0")
    )

    journal_entry: Mapped[JournalEntry] = relationship(back_populates="splits")
    account: Mapped["Account"] = relationship(back_populates="splits")  # noqa: F821

    __table_args__ = (
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(credit_amount > 0 AND debit_amount = 0)",
            name="ck_split_debit_xor_credit",
        ),
        CheckConstraint("debit_amount >= 0", name="ck_split_debit_non_negative"),
        CheckConstraint("credit_amount >= 0", name="ck_split_credit_non_negative"),
        Index("ix_splits_journal", "journal_entry_id"),
        Index("ix_splits_account", "account_id"),
    )
