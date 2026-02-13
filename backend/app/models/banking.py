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
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class ReconciliationStatus(str, enum.Enum):
    UNMATCHED = "UNMATCHED"
    MATCHED = "MATCHED"
    RECONCILED = "RECONCILED"


class BankStatementLine(Base):
    __tablename__ = "bank_statement_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus), nullable=False, default=ReconciliationStatus.UNMATCHED
    )
    matched_split_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transaction_splits.id"), nullable=True
    )
    reconciled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    matched_split = relationship("TransactionSplit")

    __table_args__ = (
        Index("ix_bsl_statement_date", "statement_date"),
        Index("ix_bsl_status", "status"),
        Index("ix_bsl_matched_split", "matched_split_id"),
    )
