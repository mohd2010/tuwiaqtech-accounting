from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Credit Invoice Creation ──────────────────────────────────────────────────


class CreditInvoiceItem(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class CreditInvoiceCreate(BaseModel):
    customer_id: UUID
    items: list[CreditInvoiceItem] = Field(min_length=1)
    invoice_date: date | None = None


# ─── Invoice Payment ─────────────────────────────────────────────────────────


class InvoicePaymentCreate(BaseModel):
    invoice_id: UUID
    amount: Decimal = Field(gt=0)
    payment_method: str = "CASH"  # CASH, CARD, BANK_TRANSFER
    payment_date: date | None = None


# ─── Response Models ─────────────────────────────────────────────────────────


class InvoicePaymentOut(BaseModel):
    id: UUID
    amount: str
    payment_date: str
    journal_entry_id: UUID

    class Config:
        from_attributes = True


class CreditInvoiceOut(BaseModel):
    id: UUID
    customer_id: UUID
    customer_name: str
    invoice_number: str
    invoice_date: str
    due_date: str
    total_amount: str
    amount_paid: str
    status: str

    class Config:
        from_attributes = True


class CreditInvoiceDetailOut(CreditInvoiceOut):
    journal_entry_id: UUID
    payments: list[InvoicePaymentOut]
    items: list[dict]
