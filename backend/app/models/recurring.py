"""Recurring journal entry templates.

A RecurringEntry stores a reusable journal-entry pattern (description,
reference prefix, splits) along with a schedule (frequency, next run date,
optional end date).  When the user clicks "Post Now", the service creates a
real JournalEntry from the template and advances `next_run_date`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
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


# ─── Enums ───────────────────────────────────────────────────────────────────


class RecurringFrequency(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUALLY = "ANNUALLY"


class RecurringStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


# ─── Models ──────────────────────────────────────────────────────────────────


class RecurringEntry(Base):
    """A template for a journal entry that repeats on a schedule."""

    __tablename__ = "recurring_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference_prefix: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequency: Mapped[RecurringFrequency] = mapped_column(
        Enum(RecurringFrequency, name="recurringfrequency", create_type=False),
        nullable=False,
    )
    next_run_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[RecurringStatus] = mapped_column(
        Enum(RecurringStatus, name="recurringstatus", create_type=False),
        nullable=False,
        default=RecurringStatus.ACTIVE,
    )
    last_posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    total_posted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    splits: Mapped[list[RecurringEntrySplit]] = relationship(
        back_populates="recurring_entry", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_recurring_entries_next_run", "next_run_date"),
        Index("ix_recurring_entries_status", "status"),
        Index("ix_recurring_entries_created_by", "created_by"),
    )


class RecurringEntrySplit(Base):
    """A single debit or credit line within a recurring entry template."""

    __tablename__ = "recurring_entry_splits"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recurring_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recurring_entries.id"), nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id"), nullable=False,
    )
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False, default=Decimal("0"),
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False, default=Decimal("0"),
    )

    recurring_entry: Mapped[RecurringEntry] = relationship(back_populates="splits")

    __table_args__ = (
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(credit_amount > 0 AND debit_amount = 0)",
            name="ck_recurring_split_debit_xor_credit",
        ),
        CheckConstraint("debit_amount >= 0", name="ck_recurring_split_debit_non_negative"),
        CheckConstraint("credit_amount >= 0", name="ck_recurring_split_credit_non_negative"),
        Index("ix_recurring_splits_entry", "recurring_entry_id"),
    )
