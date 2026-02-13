from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ─── Request Schemas ──────────────────────────────────────────────────────────


class ReturnItem(BaseModel):
    product_id: UUID
    quantity: int
    condition: str  # "RESALABLE" or "DAMAGED"

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v

    @field_validator("condition")
    @classmethod
    def condition_must_be_valid(cls, v: str) -> str:
        if v not in ("RESALABLE", "DAMAGED"):
            raise ValueError("condition must be RESALABLE or DAMAGED")
        return v


class ReturnRequest(BaseModel):
    invoice_number: str
    items: list[ReturnItem]
    reason: str

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: list[ReturnItem]) -> list[ReturnItem]:
        if len(v) == 0:
            raise ValueError("At least one return item is required")
        return v

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Reason must not be empty")
        return v


# ─── Response Schemas ─────────────────────────────────────────────────────────


class InvoiceLookupItem(BaseModel):
    product_id: str
    product_name: str
    sku: str
    quantity_sold: int
    quantity_returned: int
    returnable_quantity: int
    unit_price: str
    cost_price: str


class InvoiceLookupOut(BaseModel):
    invoice_number: str
    journal_entry_id: str
    timestamp: str
    customer_id: str | None
    items: list[InvoiceLookupItem]
    total_amount: str
    vat_amount: str
    net_amount: str


class CreditNoteItemOut(BaseModel):
    product_name: str
    quantity: int
    condition: str
    unit_refund_amount: str
    line_refund_amount: str


class CreditNoteOut(BaseModel):
    credit_note_number: str
    original_invoice_number: str
    timestamp: str
    reason: str
    items: list[CreditNoteItemOut]
    total_refund: str
    net_refund: str
    vat_refund: str
    qr_code: str
    journal_entry_id: str
