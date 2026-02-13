from __future__ import annotations

import enum
from decimal import Decimal
from uuid import UUID

from datetime import datetime

from pydantic import BaseModel, field_validator


class SplitType(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class TransactionSplitCreate(BaseModel):
    account_id: UUID
    amount: Decimal
    type: SplitType

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Split amount must be greater than zero")
        return v


class JournalEntryCreate(BaseModel):
    description: str
    reference: str | None = None
    splits: list[TransactionSplitCreate]

    @field_validator("splits")
    @classmethod
    def validate_double_entry(
        cls, v: list[TransactionSplitCreate],
    ) -> list[TransactionSplitCreate]:
        if len(v) < 2:
            raise ValueError("A journal entry requires at least two splits")

        total_debits = sum(s.amount for s in v if s.type == SplitType.DEBIT)
        total_credits = sum(s.amount for s in v if s.type == SplitType.CREDIT)

        if total_debits != total_credits:
            raise ValueError(
                f"Double-entry violation: debits ({total_debits}) "
                f"!= credits ({total_credits})"
            )

        return v


class TransactionSplitOut(BaseModel):
    id: UUID
    account_id: UUID
    debit_amount: Decimal
    credit_amount: Decimal

    class Config:
        from_attributes = True


class JournalEntryOut(BaseModel):
    id: UUID
    entry_date: datetime
    description: str
    reference: str | None
    created_by: UUID
    created_at: datetime
    splits: list[TransactionSplitOut]

    class Config:
        from_attributes = True
