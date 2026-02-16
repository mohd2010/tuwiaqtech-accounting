"""Integration tests for ZATCA e-invoicing with POS and Returns."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, AccountType, User
from backend.app.models.customer import Customer
from backend.app.models.einvoice import EInvoice, IcvCounter, InvoiceTypeCode
from backend.app.models.inventory import Product
from backend.app.models.organization import Organization
from backend.app.schemas.pos import SaleItem
from backend.app.services.pos import process_sale
from backend.app.services.returns import process_return
from backend.tests.conftest import auth


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def organization(db: Session) -> Organization:
    """Test organization with all required ZATCA fields (reuse existing if present)."""
    existing = db.query(Organization).first()
    if existing:
        existing.name_en = "Tuwaiq Outdoor"
        existing.name_ar = "تواق للأنشطة الخارجية"
        existing.vat_number = "399999999999993"
        existing.street = "King Fahd Road"
        existing.building_number = "1234"
        existing.city = "Riyadh"
        existing.district = "Al Olaya"
        existing.postal_code = "12345"
        existing.country_code = "SA"
        existing.cr_number = "1010123456"
        db.flush()
        return existing
    org = Organization(
        name_en="Tuwaiq Outdoor",
        name_ar="تواق للأنشطة الخارجية",
        vat_number="399999999999993",
        street="King Fahd Road",
        building_number="1234",
        city="Riyadh",
        district="Al Olaya",
        postal_code="12345",
        country_code="SA",
        cr_number="1010123456",
    )
    db.add(org)
    db.flush()
    return org


@pytest.fixture()
def icv_counter(db: Session) -> IcvCounter:
    """Seed the singleton ICV counter (reuse existing row if present)."""
    existing = db.query(IcvCounter).filter(IcvCounter.id == 1).first()
    if existing:
        existing.current_value = 0
        db.flush()
        return existing
    counter = IcvCounter(id=1, current_value=0)
    db.add(counter)
    db.flush()
    return counter


# ─── POS + ZATCA Integration ─────────────────────────────────────────────────


class TestSaleCreatesEInvoice:
    def test_sale_creates_einvoice(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        product_a: Product,
        admin_user: User,
        organization: Organization,
        icv_counter: IcvCounter,
    ) -> None:
        """process_sale() should create an EInvoice when org is configured."""
        result = process_sale(
            db,
            items=[SaleItem(product_id=product_a.id, quantity=2)],
            user_id=admin_user.id,
        )

        # An EInvoice should exist for this invoice
        einvoice = (
            db.query(EInvoice)
            .filter(EInvoice.invoice_number == result["invoice_number"])
            .first()
        )
        assert einvoice is not None
        assert einvoice.type_code == InvoiceTypeCode.TAX_INVOICE
        assert einvoice.icv == 1
        assert einvoice.invoice_hash != ""
        assert einvoice.qr_code != ""
        assert einvoice.total_including_vat > 0

    def test_sale_fallback_without_org(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        product_a: Product,
        admin_user: User,
    ) -> None:
        """Without org, sale should fall back to Phase 1 QR (no crash)."""
        # Remove any existing organization so e-invoice creation falls back
        db.query(Organization).delete()
        db.flush()

        einvoice_count_before = db.query(EInvoice).count()

        result = process_sale(
            db,
            items=[SaleItem(product_id=product_a.id, quantity=1)],
            user_id=admin_user.id,
        )

        assert "qr_code" in result
        assert result["qr_code"] != ""

        # No new EInvoice should have been created
        einvoice_count_after = db.query(EInvoice).count()
        assert einvoice_count_after == einvoice_count_before


class TestIcvSequential:
    def test_icv_sequential(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        product_a: Product,
        admin_user: User,
        organization: Organization,
        icv_counter: IcvCounter,
    ) -> None:
        """Each sale gets a unique incrementing ICV."""
        result1 = process_sale(
            db,
            items=[SaleItem(product_id=product_a.id, quantity=1)],
            user_id=admin_user.id,
        )
        result2 = process_sale(
            db,
            items=[SaleItem(product_id=product_a.id, quantity=1)],
            user_id=admin_user.id,
        )

        einvoice1 = (
            db.query(EInvoice)
            .filter(EInvoice.invoice_number == result1["invoice_number"])
            .first()
        )
        einvoice2 = (
            db.query(EInvoice)
            .filter(EInvoice.invoice_number == result2["invoice_number"])
            .first()
        )

        assert einvoice1 is not None
        assert einvoice2 is not None
        assert einvoice2.icv == einvoice1.icv + 1


class TestPihChain:
    def test_pih_chain(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        product_a: Product,
        admin_user: User,
        organization: Organization,
        icv_counter: IcvCounter,
    ) -> None:
        """Each invoice's PIH should be the previous invoice's hash."""
        # Clear pre-existing einvoices so the PIH chain starts fresh
        db.query(EInvoice).delete()
        db.flush()

        result1 = process_sale(
            db,
            items=[SaleItem(product_id=product_a.id, quantity=1)],
            user_id=admin_user.id,
        )
        result2 = process_sale(
            db,
            items=[SaleItem(product_id=product_a.id, quantity=1)],
            user_id=admin_user.id,
        )

        einvoice1 = (
            db.query(EInvoice)
            .filter(EInvoice.invoice_number == result1["invoice_number"])
            .first()
        )
        einvoice2 = (
            db.query(EInvoice)
            .filter(EInvoice.invoice_number == result2["invoice_number"])
            .first()
        )

        assert einvoice1 is not None
        assert einvoice2 is not None
        # Second invoice's PIH = first invoice's hash
        assert einvoice2.previous_invoice_hash == einvoice1.invoice_hash


class TestCreditNoteEInvoice:
    def test_credit_note_einvoice(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        product_a: Product,
        admin_user: User,
        organization: Organization,
        icv_counter: IcvCounter,
    ) -> None:
        """process_return() should create a type 381 EInvoice."""
        # First, make a sale
        sale_result = process_sale(
            db,
            items=[SaleItem(product_id=product_a.id, quantity=2)],
            user_id=admin_user.id,
        )

        # Then return 1 item
        return_result = process_return(
            db,
            invoice_number=sale_result["invoice_number"],
            items=[{
                "product_id": str(product_a.id),
                "quantity": 1,
                "condition": "RESALABLE",
            }],
            reason="Defective",
            user_id=admin_user.id,
        )

        # Find credit note einvoice
        cn_einvoice = (
            db.query(EInvoice)
            .filter(EInvoice.invoice_number == return_result["credit_note_number"])
            .first()
        )
        assert cn_einvoice is not None
        assert cn_einvoice.type_code == InvoiceTypeCode.CREDIT_NOTE
        assert cn_einvoice.qr_code != ""


class TestOrganizationCrud:
    def test_organization_crud(
        self,
        client,
        db: Session,
        admin_token: str,
    ) -> None:
        """API create/get organization."""
        # Clear any pre-existing organization
        db.query(Organization).delete()
        db.flush()

        org_data = {
            "name_en": "Test Corp",
            "name_ar": "شركة اختبار",
            "vat_number": "399999999999993",
            "street": "Test St",
            "building_number": "1234",
            "city": "Riyadh",
            "district": "Test District",
            "postal_code": "12345",
            "country_code": "SA",
        }

        # Create
        resp = client.put("/api/v1/organization", json=org_data, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name_en"] == "Test Corp"
        assert data["vat_number"] == "399999999999993"
        assert data["has_certificate"] is False

        # Get
        resp = client.get("/api/v1/organization", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["name_en"] == "Test Corp"
