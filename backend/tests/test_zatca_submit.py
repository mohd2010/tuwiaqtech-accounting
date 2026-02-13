"""Integration tests for e-invoice submission and onboarding endpoints."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.accounting import JournalEntry, User
from backend.app.models.einvoice import (
    EInvoice,
    InvoiceSubType,
    InvoiceTypeCode,
    ZatcaSubmissionStatus,
)
from backend.app.models.organization import Organization
from backend.tests.conftest import auth


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_org(db: Session, **overrides: object) -> Organization:
    defaults = dict(
        name_en="Test Corp",
        name_ar="شركة اختبار",
        vat_number="300000000000003",
        street="Test St",
        building_number="1234",
        city="Riyadh",
        district="Al Olaya",
        postal_code="12345",
        country_code="SA",
        csid="test-csid-token",
        certificate_serial="test-secret",
        private_key_pem=b"fake-key-pem",
        is_production=False,
    )
    defaults.update(overrides)
    org = Organization(**defaults)  # type: ignore[arg-type]
    db.add(org)
    db.flush()
    return org


_ICV_SEQ = 0


def _make_einvoice(
    db: Session,
    *,
    user: User | None = None,
    sub_type: InvoiceSubType = InvoiceSubType.SIMPLIFIED,
    status: ZatcaSubmissionStatus = ZatcaSubmissionStatus.PENDING,
    invoice_number: str = "INV-001",
) -> EInvoice:
    global _ICV_SEQ  # noqa: PLW0603
    _ICV_SEQ += 1

    # Create a journal entry to satisfy FK constraint
    if user is None:
        from backend.app.core.security import get_password_hash
        from backend.app.models.accounting import RoleEnum

        user = User(
            username=f"test_user_{_ICV_SEQ}",
            hashed_password=get_password_hash("pass"),
            role=RoleEnum.ADMIN,
        )
        db.add(user)
        db.flush()

    je = JournalEntry(
        entry_date=datetime.now(timezone.utc),
        description=f"Test entry for {invoice_number}",
        created_by=user.id,
    )
    db.add(je)
    db.flush()

    einvoice = EInvoice(
        journal_entry_id=je.id,
        invoice_uuid=str(uuid.uuid4()),
        invoice_number=invoice_number,
        icv=_ICV_SEQ,
        type_code=InvoiceTypeCode.TAX_INVOICE,
        sub_type=sub_type,
        invoice_hash="a" * 64,
        previous_invoice_hash="0" * 64,
        xml_content=b"<Invoice>test</Invoice>",
        qr_code="QRDATA",
        total_excluding_vat=Decimal("100.0000"),
        total_vat=Decimal("15.0000"),
        total_including_vat=Decimal("115.0000"),
        submission_status=status,
        issue_date=datetime.now(timezone.utc),
    )
    db.add(einvoice)
    db.flush()
    return einvoice


# Patch target: the class at its source module (endpoints import it locally)
_API_CLIENT_PATH = "backend.app.services.zatca.api_client.ZatcaApiClient"


# ─── Submit Endpoint Tests ──────────────────────────────────────────────────


class TestSubmitSimplifiedInvoice:
    """POST /api/v1/einvoices/{invoice_number}/submit — B2C reporting."""

    @patch(_API_CLIENT_PATH)
    def test_reported_success(
        self,
        MockClient: AsyncMock,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        _make_org(db)
        einvoice = _make_einvoice(db, sub_type=InvoiceSubType.SIMPLIFIED)

        mock_instance = MockClient.return_value
        mock_instance.report_simplified_invoice = AsyncMock(return_value={
            "reportingStatus": "REPORTED",
            "requestID": "req-001",
            "validationResults": {"warningMessages": [], "errorMessages": []},
        })

        resp = client.post(
            f"/api/v1/einvoices/{einvoice.invoice_number}/submit",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["submission_status"] == "REPORTED"
        assert data["zatca_reporting_status"] == "REPORTED"

    @patch(_API_CLIENT_PATH)
    def test_not_reported_becomes_rejected(
        self,
        MockClient: AsyncMock,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        _make_org(db)
        einvoice = _make_einvoice(db, sub_type=InvoiceSubType.SIMPLIFIED)

        mock_instance = MockClient.return_value
        mock_instance.report_simplified_invoice = AsyncMock(return_value={
            "reportingStatus": "NOT_REPORTED",
            "requestID": "req-002",
            "validationResults": {
                "errorMessages": [{"message": "Invalid hash"}],
                "warningMessages": [],
            },
        })

        resp = client.post(
            f"/api/v1/einvoices/{einvoice.invoice_number}/submit",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["submission_status"] == "REJECTED"
        assert data["zatca_errors"] is not None


class TestSubmitStandardInvoice:
    """POST /api/v1/einvoices/{invoice_number}/submit — B2B clearance."""

    @patch(_API_CLIENT_PATH)
    def test_cleared_success_stores_xml(
        self,
        MockClient: AsyncMock,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        _make_org(db)
        einvoice = _make_einvoice(
            db, sub_type=InvoiceSubType.STANDARD, invoice_number="INV-B2B-001"
        )

        cleared_xml = base64.b64encode(b"<Invoice>ZATCA-stamped</Invoice>").decode()
        mock_instance = MockClient.return_value
        mock_instance.clear_standard_invoice = AsyncMock(return_value={
            "clearanceStatus": "CLEARED",
            "clearedInvoice": cleared_xml,
            "requestID": "req-003",
            "validationResults": {"warningMessages": [], "errorMessages": []},
        })

        resp = client.post(
            f"/api/v1/einvoices/{einvoice.invoice_number}/submit",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["submission_status"] == "CLEARED"
        assert data["zatca_clearance_status"] == "CLEARED"

        # Verify cleared XML was stored
        db.refresh(einvoice)
        assert einvoice.xml_content == b"<Invoice>ZATCA-stamped</Invoice>"

    @patch(_API_CLIENT_PATH)
    def test_not_cleared_becomes_rejected(
        self,
        MockClient: AsyncMock,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        _make_org(db)
        einvoice = _make_einvoice(
            db, sub_type=InvoiceSubType.STANDARD, invoice_number="INV-B2B-002"
        )

        mock_instance = MockClient.return_value
        mock_instance.clear_standard_invoice = AsyncMock(return_value={
            "clearanceStatus": "NOT_CLEARED",
            "requestID": "req-004",
            "validationResults": {
                "errorMessages": [{"message": "Buyer VAT not found"}],
                "warningMessages": [],
            },
        })

        resp = client.post(
            f"/api/v1/einvoices/{einvoice.invoice_number}/submit",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["submission_status"] == "REJECTED"


class TestSubmitEdgeCases:
    """Validation and edge-case tests for the submit endpoint."""

    def test_submit_without_credentials(
        self,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        # No org → no credentials
        einvoice = _make_einvoice(db, invoice_number="INV-NO-CREDS")

        resp = client.post(
            f"/api/v1/einvoices/{einvoice.invoice_number}/submit",
            headers=auth(admin_token),
        )
        assert resp.status_code == 400
        assert "ZATCA credentials" in resp.json()["detail"]

    def test_submit_already_cleared(
        self,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        _make_org(db)
        einvoice = _make_einvoice(
            db,
            status=ZatcaSubmissionStatus.CLEARED,
            invoice_number="INV-ALREADY",
        )

        resp = client.post(
            f"/api/v1/einvoices/{einvoice.invoice_number}/submit",
            headers=auth(admin_token),
        )
        assert resp.status_code == 400
        assert "Cannot submit" in resp.json()["detail"]

    @patch(_API_CLIENT_PATH)
    def test_submit_can_retry_rejected(
        self,
        MockClient: AsyncMock,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        _make_org(db)
        einvoice = _make_einvoice(
            db,
            status=ZatcaSubmissionStatus.REJECTED,
            invoice_number="INV-RETRY",
        )

        mock_instance = MockClient.return_value
        mock_instance.report_simplified_invoice = AsyncMock(return_value={
            "reportingStatus": "REPORTED",
            "requestID": "req-retry",
            "validationResults": {"warningMessages": [], "errorMessages": []},
        })

        resp = client.post(
            f"/api/v1/einvoices/{einvoice.invoice_number}/submit",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["submission_status"] == "REPORTED"

    def test_submit_nonexistent_invoice(
        self,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        resp = client.post(
            "/api/v1/einvoices/DOES-NOT-EXIST/submit",
            headers=auth(admin_token),
        )
        assert resp.status_code == 404


# ─── Compliance Check Endpoint Tests ────────────────────────────────────────


class TestComplianceCheck:
    """POST /api/v1/zatca/compliance-check."""

    @patch(_API_CLIENT_PATH)
    def test_compliance_check_success(
        self,
        MockClient: AsyncMock,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        _make_org(db)
        einvoice = _make_einvoice(db, invoice_number="INV-COMP-001")

        mock_instance = MockClient.return_value
        mock_instance.check_compliance_invoice = AsyncMock(return_value={
            "reportingStatus": "REPORTED",
            "requestID": "req-comp-001",
            "validationResults": {"warningMessages": [], "errorMessages": []},
        })

        resp = client.post(
            "/api/v1/zatca/compliance-check",
            json={"invoice_number": "INV-COMP-001"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reporting_status"] == "REPORTED"
        assert data["request_id"] == "req-comp-001"

    def test_compliance_check_no_credentials(
        self,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        # Org without CSID
        _make_org(db, csid=None, certificate_serial=None)
        _make_einvoice(db, invoice_number="INV-COMP-002")

        resp = client.post(
            "/api/v1/zatca/compliance-check",
            json={"invoice_number": "INV-COMP-002"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 400
        assert "ZATCA credentials" in resp.json()["detail"]

    def test_compliance_check_invoice_not_found(
        self,
        client: TestClient,
        db: Session,
        admin_token: str,
    ) -> None:
        _make_org(db)

        resp = client.post(
            "/api/v1/zatca/compliance-check",
            json={"invoice_number": "NONEXISTENT"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 404
