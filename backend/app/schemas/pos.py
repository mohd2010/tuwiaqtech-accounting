from __future__ import annotations

from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


# ─── Payment Method ──────────────────────────────────────────────────────────


class PaymentMethodEnum(str, Enum):
    CASH = "CASH"
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"


class DiscountTypeEnum(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class PaymentEntry(BaseModel):
    method: PaymentMethodEnum
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Payment amount must be greater than zero")
        return v


class PaymentEntryOut(BaseModel):
    method: str
    amount: str


# ─── Request ──────────────────────────────────────────────────────────────────


class SaleItem(BaseModel):
    product_id: UUID
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v


class SaleRequest(BaseModel):
    items: list[SaleItem]
    customer_id: UUID | None = None
    payments: list[PaymentEntry] | None = None
    discount_type: DiscountTypeEnum | None = None
    discount_value: Decimal | None = None

    @field_validator("items")
    @classmethod
    def at_least_one_item(cls, v: list[SaleItem]) -> list[SaleItem]:
        if not v:
            raise ValueError("Cart must contain at least one item")
        return v

    @field_validator("discount_value")
    @classmethod
    def discount_value_positive(cls, v: Decimal | None, info: object) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("Discount value must be greater than zero")
        return v

    @model_validator(mode="after")
    def validate_discount(self) -> "SaleRequest":
        if self.discount_type and not self.discount_value:
            raise ValueError("discount_value is required when discount_type is set")
        if self.discount_value and not self.discount_type:
            raise ValueError("discount_type is required when discount_value is set")
        if (
            self.discount_type == DiscountTypeEnum.PERCENTAGE
            and self.discount_value is not None
            and self.discount_value >= 100
        ):
            raise ValueError("Percentage discount must be less than 100")
        return self


# ─── Response ─────────────────────────────────────────────────────────────────


class InvoiceLineOut(BaseModel):
    product: str
    quantity: int
    unit_price: str
    line_total: str


class InvoiceOut(BaseModel):
    invoice_number: str
    timestamp: str
    items: list[InvoiceLineOut]
    total_collected: str
    net_revenue: str
    vat_amount: str
    qr_code: str
    journal_entry_id: str
    payments: list[PaymentEntryOut] = []
    discount_amount: str = "0"
    original_total: str = ""


# ─── Barcode scan ─────────────────────────────────────────────────────────────


class ScanRequest(BaseModel):
    barcode: str


class ScanProductOut(BaseModel):
    id: UUID
    name: str
    sku: str
    unit_price: Decimal
    current_stock: int

    class Config:
        from_attributes = True


# ─── Registers & Shifts ─────────────────────────────────────────────────────


class RegisterOut(BaseModel):
    id: UUID
    name: str
    location: str | None
    warehouse_id: UUID | None = None
    warehouse_name: str | None = None

    class Config:
        from_attributes = True


class ShiftOpenRequest(BaseModel):
    register_id: UUID
    opening_cash: Decimal

    @field_validator("opening_cash")
    @classmethod
    def cash_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Opening cash must be non-negative")
        return v


class ShiftCloseRequest(BaseModel):
    closing_cash_reported: Decimal
    notes: str | None = None

    @field_validator("closing_cash_reported")
    @classmethod
    def cash_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Closing cash must be non-negative")
        return v


class ShiftOut(BaseModel):
    id: UUID
    register_id: UUID
    register_name: str
    user_id: UUID
    username: str
    status: str
    opened_at: str
    closed_at: str | None
    opening_cash: str
    closing_cash_reported: str | None
    expected_cash: str | None
    discrepancy: str | None
    total_sales: str
    notes: str | None
