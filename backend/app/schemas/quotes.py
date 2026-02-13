from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ─── Request ──────────────────────────────────────────────────────────────────


class QuoteItemCreate(BaseModel):
    product_id: UUID
    quantity: int
    unit_price: Decimal

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v

    @field_validator("unit_price")
    @classmethod
    def price_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Unit price must be greater than zero")
        return v


class QuoteCreate(BaseModel):
    customer_name: str
    customer_vat: str | None = None
    expiry_date: date
    notes: str | None = None
    items: list[QuoteItemCreate]

    @field_validator("customer_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Customer name is required")
        return v.strip()

    @field_validator("items")
    @classmethod
    def at_least_one(cls, v: list[QuoteItemCreate]) -> list[QuoteItemCreate]:
        if not v:
            raise ValueError("Quote must have at least one item")
        return v


class QuoteStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        allowed = {"SENT", "ACCEPTED", "REJECTED"}
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(sorted(allowed))}")
        return v


# ─── Response ─────────────────────────────────────────────────────────────────


class QuoteItemOut(BaseModel):
    id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: str
    line_total: str


class QuoteOut(BaseModel):
    id: str
    quote_number: str
    customer_name: str
    customer_vat: str | None
    status: str
    expiry_date: str
    total_amount: str
    notes: str | None
    invoice_number: str | None
    created_by: str
    created_at: str
    items: list[QuoteItemOut]


class QuoteListOut(BaseModel):
    id: str
    quote_number: str
    customer_name: str
    status: str
    expiry_date: str
    total_amount: str
    item_count: int
    created_at: str


class QuoteConvertOut(BaseModel):
    quote_id: str
    quote_number: str
    invoice_number: str
    invoice_data: dict
