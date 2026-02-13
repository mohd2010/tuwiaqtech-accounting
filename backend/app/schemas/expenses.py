from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class ExpenseCreate(BaseModel):
    description: str
    amount: Decimal
    expense_account_id: UUID
    payment_account_id: UUID
    date: str | None = None

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description must not be empty")
        return v

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v


class ExpenseOut(BaseModel):
    id: str
    reference: str
    description: str
    amount: str
    expense_account_name: str
    payment_account_name: str
    date: str
    created_by: str
