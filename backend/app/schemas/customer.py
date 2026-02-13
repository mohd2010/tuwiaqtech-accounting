from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


# ─── Customer CRUD ────────────────────────────────────────────────────────────


class CustomerCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    vat_number: str | None = None
    credit_limit: Decimal | None = None
    payment_terms_days: int = 30
    # ZATCA address fields
    street: str | None = None
    building_number: str | None = None
    city: str | None = None
    district: str | None = None
    postal_code: str | None = None
    country_code: str | None = "SA"
    additional_id: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    vat_number: str | None = None
    credit_limit: Decimal | None = None
    payment_terms_days: int | None = None
    # ZATCA address fields
    street: str | None = None
    building_number: str | None = None
    city: str | None = None
    district: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    additional_id: str | None = None


class CustomerOut(BaseModel):
    id: UUID
    name: str
    email: str | None
    phone: str | None
    vat_number: str | None
    credit_limit: str | None
    payment_terms_days: int
    total_spent: str
    last_purchase_at: datetime | None
    # ZATCA address fields
    street: str | None = None
    building_number: str | None = None
    city: str | None = None
    district: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    additional_id: str | None = None

    class Config:
        from_attributes = True


# ─── Sale / Purchase History ──────────────────────────────────────────────────


class SaleOut(BaseModel):
    id: UUID
    invoice_number: str
    product_name: str
    quantity: int
    total_amount: str
    date: datetime


class CustomerDetailOut(CustomerOut):
    """Customer with purchase history attached."""

    purchases: list[SaleOut]
