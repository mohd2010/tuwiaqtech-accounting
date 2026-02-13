from __future__ import annotations

from pydantic import BaseModel


class SaleLineOut(BaseModel):
    product: str
    quantity: int
    unit_price: str
    line_total: str


class SaleDetailOut(BaseModel):
    invoice_number: str
    timestamp: str
    journal_entry_id: str
    items: list[SaleLineOut]
    total_collected: str
    net_revenue: str
    vat_amount: str
    qr_code: str
    discount_amount: str = "0"
    original_total: str = ""


class SaleHistoryOut(BaseModel):
    id: str
    invoice_number: str
    date: str
    customer_name: str | None
    cashier: str
    item_count: int
    total_amount: str
    net_amount: str
    vat_amount: str
    status: str
    discount_amount: str = "0"
