from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EInvoiceOut(BaseModel):
    id: UUID
    invoice_uuid: str
    invoice_number: str
    icv: int
    type_code: str
    sub_type: str
    total_excluding_vat: str
    total_vat: str
    total_including_vat: str
    buyer_name: str | None
    buyer_vat_number: str | None
    submission_status: str
    zatca_clearance_status: str | None
    zatca_reporting_status: str | None
    zatca_warnings: dict | None
    zatca_errors: dict | None
    submitted_at: datetime | None
    issue_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class EInvoiceXmlOut(BaseModel):
    invoice_number: str
    xml_content: str  # base64 encoded


class EInvoiceListOut(BaseModel):
    items: list[EInvoiceOut]
    total: int


class EInvoiceSummaryOut(BaseModel):
    total: int
    pending: int
    cleared: int
    reported: int
    rejected: int
    warning: int
