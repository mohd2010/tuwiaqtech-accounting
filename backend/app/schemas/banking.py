from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ─── Statement Entry ─────────────────────────────────────────────────────────


class BankStatementLineCreate(BaseModel):
    statement_date: date
    description: str
    amount: Decimal
    reference: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_nonzero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("Amount must not be zero")
        return v


class BankStatementLineBulkCreate(BaseModel):
    lines: list[BankStatementLineCreate]

    @field_validator("lines")
    @classmethod
    def at_least_one_line(cls, v: list[BankStatementLineCreate]) -> list[BankStatementLineCreate]:
        if not v:
            raise ValueError("Must provide at least one statement line")
        return v


class BankStatementLineOut(BaseModel):
    id: UUID
    statement_date: str
    description: str
    amount: str
    reference: str | None
    status: str
    matched_split_id: UUID | None
    matched_journal_ref: str | None = None
    matched_journal_date: str | None = None
    reconciled_by: UUID | None
    reconciled_at: str | None
    created_at: str


# ─── Match / Unmatch / Reconcile ─────────────────────────────────────────────


class MatchRequest(BaseModel):
    statement_line_id: UUID
    split_id: UUID


class UnmatchRequest(BaseModel):
    statement_line_id: UUID


class ReconcileRequest(BaseModel):
    statement_line_ids: list[UUID]

    @field_validator("statement_line_ids")
    @classmethod
    def at_least_one(cls, v: list[UUID]) -> list[UUID]:
        if not v:
            raise ValueError("Must provide at least one statement line ID")
        return v


# ─── Summary ─────────────────────────────────────────────────────────────────


class BankReconciliationSummary(BaseModel):
    gl_balance: str
    statement_balance: str
    reconciled_balance: str
    unmatched_count: int
    matched_count: int
    reconciled_count: int


# ─── Unreconciled Splits ─────────────────────────────────────────────────────


class UnreconciledSplitOut(BaseModel):
    split_id: UUID
    journal_entry_id: UUID
    journal_ref: str | None
    journal_date: str
    description: str
    debit_amount: str
    credit_amount: str
    net_amount: str
