from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class FiscalClose(Base):
    """Records the closing of a fiscal year.

    When a fiscal year is closed, a closing journal entry zeros out all
    Revenue and Expense accounts into Retained Earnings (3000).
    No further journal entries may be dated within that closed year.
    """

    __tablename__ = "fiscal_closes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    fiscal_year: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    close_date: Mapped[date] = mapped_column(Date, nullable=False)
    closing_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False,
    )
    closed_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False,
    )
    closed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
