from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    LargeBinary,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class Organization(Base):
    """Seller / organization info for ZATCA e-invoicing.

    Singleton-style: the system expects exactly one row.
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    vat_number: Mapped[str] = mapped_column(String(15), nullable=False)
    additional_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cr_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Address (ZATCA-required)
    street: Mapped[str] = mapped_column(String(255), nullable=False)
    building_number: Mapped[str] = mapped_column(String(4), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    district: Mapped[str] = mapped_column(String(255), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(5), nullable=False)
    province: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="SA")

    # ZATCA cryptographic material
    private_key_pem: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    csr_pem: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    certificate_pem: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    csid: Mapped[str | None] = mapped_column(Text, nullable=True)
    certificate_serial: Mapped[str | None] = mapped_column(String(255), nullable=True)
    compliance_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Onboarding step tracking:
    # CSR_GENERATED → COMPLIANCE_CSID_ISSUED → COMPLIANCE_CHECKED → PRODUCTION_READY
    onboarding_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Environment
    is_production: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    zatca_api_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
