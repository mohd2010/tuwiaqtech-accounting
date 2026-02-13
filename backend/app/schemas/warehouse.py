from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, field_validator


# ─── Warehouse ────────────────────────────────────────────────────────────────


class WarehouseCreate(BaseModel):
    name: str
    address: str | None = None


class WarehouseUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    is_active: bool | None = None


class WarehouseOut(BaseModel):
    id: UUID
    name: str
    address: str | None
    is_active: bool

    class Config:
        from_attributes = True


# ─── Stock at Warehouse ───────────────────────────────────────────────────────


class WarehouseStockOut(BaseModel):
    product_id: UUID
    product_name: str
    product_sku: str
    quantity: int


# ─── Transfers ────────────────────────────────────────────────────────────────


class TransferItemCreate(BaseModel):
    product_id: UUID
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v


class TransferCreate(BaseModel):
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    items: list[TransferItemCreate]
    notes: str | None = None

    @field_validator("items")
    @classmethod
    def at_least_one_item(cls, v: list[TransferItemCreate]) -> list[TransferItemCreate]:
        if not v:
            raise ValueError("Transfer must contain at least one item")
        return v


class TransferItemOut(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    product_sku: str
    quantity: int


class TransferOut(BaseModel):
    id: UUID
    from_warehouse_id: UUID
    from_warehouse_name: str
    to_warehouse_id: UUID
    to_warehouse_name: str
    status: str
    notes: str | None
    items: list[TransferItemOut]
    created_by_username: str
    created_at: str
    updated_at: str
