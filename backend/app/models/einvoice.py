from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class InvoiceTypeCode(str, enum.Enum):
    TAX_INVOICE = "388"
    CREDIT_NOTE = "381"
    DEBIT_NOTE = "383"
    PREPAYMENT = "386"


class InvoiceSubType(str, enum.Enum):
    STANDARD = "0100000"
    SIMPLIFIED = "0200000"


class ZatcaSubmissionStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CLEARED = "CLEARED"
    REPORTED = "REPORTED"
    REJECTED = "REJECTED"
    WARNING = "WARNING"


class EInvoice(Base):
    __tablename__ = "einvoices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=False
    )
    credit_note_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("credit_notes.id"), nullable=True
    )

    # ZATCA identifiers
    invoice_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    icv: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)

    # Type — values_callable ensures SQLAlchemy uses enum .value (matching PG enum)
    type_code: Mapped[InvoiceTypeCode] = mapped_column(
        Enum(
            InvoiceTypeCode,
            name="invoicetypecode",
            create_constraint=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    sub_type: Mapped[InvoiceSubType] = mapped_column(
        Enum(
            InvoiceSubType,
            name="invoicesubtype",
            create_constraint=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )

    # Cryptographic
    invoice_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    previous_invoice_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    xml_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    qr_code: Mapped[str] = mapped_column(Text, nullable=False)

    # Totals
    total_excluding_vat: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    total_vat: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    total_including_vat: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )

    # Buyer
    buyer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer_vat_number: Mapped[str | None] = mapped_column(String(15), nullable=True)

    # ZATCA submission
    submission_status: Mapped[ZatcaSubmissionStatus] = mapped_column(
        Enum(
            ZatcaSubmissionStatus,
            name="zatcasubmissionstatus",
            create_constraint=False,
        ),
        nullable=False,
        default=ZatcaSubmissionStatus.PENDING,
    )
    zatca_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zatca_clearance_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    zatca_reporting_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    zatca_warnings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    zatca_errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Dates
    issue_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    supply_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_einvoices_invoice_number", "invoice_number"),
        Index("ix_einvoices_submission_status", "submission_status"),
        Index("ix_einvoices_issue_date", "issue_date"),
        Index("ix_einvoices_journal_entry_id", "journal_entry_id"),
    )


class IcvCounter(Base):
    """Singleton row for atomic ICV (Invoice Counter Value) increments."""

    __tablename__ = "icv_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
