from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ─── Supplier ─────────────────────────────────────────────────────────────────


class SupplierCreate(BaseModel):
    name: str
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    vat_number: str | None = None
    address: str | None = None


class SupplierOut(BaseModel):
    id: UUID
    name: str
    contact_person: str | None
    email: str | None
    phone: str | None
    vat_number: str | None
    address: str | None

    class Config:
        from_attributes = True


# ─── Purchase Order ───────────────────────────────────────────────────────────


class POItemCreate(BaseModel):
    product_id: UUID
    quantity: int
    unit_cost: Decimal

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v

    @field_validator("unit_cost")
    @classmethod
    def cost_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Unit cost must be non-negative")
        return v


class POItemOut(BaseModel):
    id: UUID
    product_id: UUID
    quantity: int
    unit_cost: Decimal

    class Config:
        from_attributes = True


class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID
    items: list[POItemCreate]

    @field_validator("items")
    @classmethod
    def at_least_one_item(cls, v: list[POItemCreate]) -> list[POItemCreate]:
        if len(v) == 0:
            raise ValueError("Purchase order must have at least one item")
        return v


class PurchaseOrderOut(BaseModel):
    id: UUID
    supplier_id: UUID
    status: str
    total_amount: Decimal
    created_at: datetime
    items: list[POItemOut]

    class Config:
        from_attributes = True


# ─── Purchase Return ─────────────────────────────────────────────────────────


class PurchaseReturnItemIn(BaseModel):
    product_id: UUID
    quantity: int
    condition: str  # "RESALABLE" or "DAMAGED"

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v

    @field_validator("condition")
    @classmethod
    def condition_valid(cls, v: str) -> str:
        if v not in ("RESALABLE", "DAMAGED"):
            raise ValueError("condition must be RESALABLE or DAMAGED")
        return v


class PurchaseReturnRequest(BaseModel):
    po_id: UUID
    items: list[PurchaseReturnItemIn]
    reason: str

    @field_validator("items")
    @classmethod
    def at_least_one_item(cls, v: list[PurchaseReturnItemIn]) -> list[PurchaseReturnItemIn]:
        if len(v) == 0:
            raise ValueError("At least one return item is required")
        return v

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Reason must not be empty")
        return v


class PurchaseReturnItemOut(BaseModel):
    product_name: str
    quantity: int
    condition: str
    unit_cost: str
    line_total: str


class PurchaseReturnOut(BaseModel):
    return_number: str
    po_id: str
    supplier_name: str
    timestamp: str
    reason: str
    items: list[PurchaseReturnItemOut]
    total_amount: str
    journal_entry_id: str


class POLookupItemOut(BaseModel):
    product_id: str
    product_name: str
    sku: str
    quantity_ordered: int
    quantity_returned: int
    returnable_quantity: int
    unit_cost: str


class POLookupOut(BaseModel):
    po_id: str
    supplier_name: str
    received_at: str
    items: list[POLookupItemOut]
    total_amount: str
