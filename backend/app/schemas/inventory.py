from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class CategoryCreate(BaseModel):
    name: str
    description: str | None = None


class CategoryOut(BaseModel):
    id: UUID
    name: str
    description: str | None

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    name: str
    sku: str
    category_id: UUID
    description: str | None = None
    unit_price: Decimal
    cost_price: Decimal
    reorder_level: int = 0
    # NOTE: No `current_stock` field. Initial stock must be recorded via a
    # Journal Entry (Debit Inventory / Credit Owner's Equity) — to be
    # implemented in the inventory service.

    @field_validator("unit_price", "cost_price")
    @classmethod
    def price_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Price must be non-negative")
        return v


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    unit_price: Decimal | None = None
    cost_price: Decimal | None = None
    reorder_level: int | None = None
    # NOTE: current_stock is intentionally excluded. Stock changes must go
    # through journal entries to maintain double-entry integrity.

    @field_validator("unit_price", "cost_price")
    @classmethod
    def price_non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("Price must be non-negative")
        return v


class StockInRequest(BaseModel):
    quantity: int
    total_cost: Decimal
    payment_account_id: UUID

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v

    @field_validator("total_cost")
    @classmethod
    def cost_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Total cost must be greater than zero")
        return v


class ProductOut(BaseModel):
    id: UUID
    name: str
    sku: str
    category_id: UUID
    description: str | None
    unit_price: Decimal
    cost_price: Decimal
    current_stock: int
    reorder_level: int

    class Config:
        from_attributes = True


# ─── Stock Adjustments ──────────────────────────────────────────────────────


class StockAdjustmentCreate(BaseModel):
    product_id: UUID
    adjustment_type: str  # DAMAGE | THEFT | COUNT_ERROR | PROMOTION
    quantity: int
    notes: str | None = None

    @field_validator("adjustment_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        allowed = {"DAMAGE", "THEFT", "COUNT_ERROR", "PROMOTION"}
        if v not in allowed:
            raise ValueError(f"adjustment_type must be one of {allowed}")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Quantity must not be zero")
        return v


class StockAdjustmentOut(BaseModel):
    id: UUID
    product_name: str
    product_sku: str
    adjustment_type: str
    quantity: int
    notes: str | None
    created_by_username: str
    created_at: str
