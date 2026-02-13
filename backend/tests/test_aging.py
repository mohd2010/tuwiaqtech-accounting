"""Tests for AR and AP aging reports."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, User
from backend.app.models.customer import Customer
from backend.app.models.inventory import Product
from backend.app.models.invoice import CreditInvoice, InvoiceStatus
from backend.app.models.supplier import POStatus, PurchaseOrder, Supplier
from backend.app.services.aging import get_ap_aging, get_ar_aging
from backend.app.services.credit_invoice import (
    create_credit_invoice,
    record_invoice_payment,
)
from backend.tests.conftest import auth

ZERO = Decimal("0")


# ─── AR Aging Tests ──────────────────────────────────────────────────────────


class TestARAgingReport:
    def test_empty_aging(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
    ) -> None:
        result = get_ar_aging(db, date.today())
        assert result["kpi"]["total_receivable"] == "0"
        assert result["kpi"]["total_overdue"] == "0"
        assert len(result["customers"]) == 0

    def test_current_bucket(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        """An invoice not yet due should appear in the current bucket."""
        create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 1}],
            user_id=admin_user.id,
        )
        result = get_ar_aging(db, date.today())
        assert Decimal(result["kpi"]["total_receivable"]) == Decimal("100.0000")
        assert len(result["customers"]) == 1
        row = result["customers"][0]
        assert Decimal(row["current"]) == Decimal("100.0000")
        assert Decimal(row["over_90"]) == ZERO

    def test_overdue_buckets(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        """Create an invoice with due_date 45 days ago → 31-60 bucket."""
        now = datetime.now(timezone.utc)
        inv = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 1}],
            user_id=admin_user.id,
        )
        # Manually set due_date to 45 days ago
        invoice = db.query(CreditInvoice).filter(
            CreditInvoice.invoice_number == inv["invoice_number"]
        ).first()
        invoice.due_date = now - timedelta(days=45)
        db.flush()

        result = get_ar_aging(db, date.today())
        row = result["customers"][0]
        assert Decimal(row["days_31_60"]) == Decimal("100.0000")
        assert Decimal(result["kpi"]["total_overdue"]) == Decimal("100.0000")

    def test_partial_payment_reduces_outstanding(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        inv = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 2}],
            user_id=admin_user.id,
        )
        from uuid import UUID
        record_invoice_payment(
            db,
            invoice_id=UUID(inv["id"]),
            amount=Decimal("50.0000"),
            payment_method="CASH",
            user_id=admin_user.id,
        )
        result = get_ar_aging(db, date.today())
        # 200 - 50 = 150 outstanding
        assert Decimal(result["kpi"]["total_receivable"]) == Decimal("150.0000")

    def test_paid_invoice_excluded(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        inv = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 1}],
            user_id=admin_user.id,
        )
        from uuid import UUID
        record_invoice_payment(
            db,
            invoice_id=UUID(inv["id"]),
            amount=Decimal("100.0000"),
            payment_method="CASH",
            user_id=admin_user.id,
        )
        result = get_ar_aging(db, date.today())
        assert Decimal(result["kpi"]["total_receivable"]) == ZERO
        assert len(result["customers"]) == 0

    def test_totals_match(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
        product_b: Product,
    ) -> None:
        create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 1}],
            user_id=admin_user.id,
        )
        create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_b.id, "quantity": 1}],
            user_id=admin_user.id,
        )
        result = get_ar_aging(db, date.today())
        # 100 + 200 = 300
        assert Decimal(result["totals"]["total"]) == Decimal("300.0000")
        assert Decimal(result["kpi"]["total_receivable"]) == Decimal("300.0000")

    def test_cashier_forbidden(
        self,
        client: TestClient,
        cashier_token: str,
    ) -> None:
        resp = client.get(
            "/api/v1/reports/ar-aging",
            headers=auth(cashier_token),
        )
        assert resp.status_code == 403


# ─── AP Aging Tests ──────────────────────────────────────────────────────────


class TestAPAgingReport:
    def test_empty_aging(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
    ) -> None:
        result = get_ap_aging(db, date.today())
        assert result["kpi"]["total_payable"] == "0"
        assert len(result["suppliers"]) == 0

    def test_recent_po_in_current_bucket(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
    ) -> None:
        supplier = Supplier(name="Test Supplier", email="s@test.com")
        db.add(supplier)
        db.flush()

        po = PurchaseOrder(
            supplier_id=supplier.id,
            status=POStatus.RECEIVED,
            total_amount=Decimal("1000.0000"),
            created_by=admin_user.id,
        )
        db.add(po)
        db.flush()

        result = get_ap_aging(db, date.today())
        assert len(result["suppliers"]) == 1
        assert Decimal(result["suppliers"][0]["current"]) == Decimal("1000.0000")

    def test_old_po_in_over_90(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
    ) -> None:
        supplier = Supplier(name="Old Supplier", email="old@test.com")
        db.add(supplier)
        db.flush()

        now = datetime.now(timezone.utc)
        po = PurchaseOrder(
            supplier_id=supplier.id,
            status=POStatus.RECEIVED,
            total_amount=Decimal("500.0000"),
            created_by=admin_user.id,
        )
        db.add(po)
        db.flush()
        # Set created_at to 100 days ago
        po.created_at = now - timedelta(days=100)
        db.flush()

        result = get_ap_aging(db, date.today())
        assert len(result["suppliers"]) == 1
        assert Decimal(result["suppliers"][0]["over_90"]) == Decimal("500.0000")
        assert Decimal(result["kpi"]["total_overdue"]) == Decimal("500.0000")

    def test_totals_match(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
    ) -> None:
        supplier = Supplier(name="Multi PO Supplier", email="multi@test.com")
        db.add(supplier)
        db.flush()

        for amount in [Decimal("100.0000"), Decimal("200.0000")]:
            po = PurchaseOrder(
                supplier_id=supplier.id,
                status=POStatus.RECEIVED,
                total_amount=amount,
                created_by=admin_user.id,
            )
            db.add(po)
        db.flush()

        result = get_ap_aging(db, date.today())
        assert Decimal(result["totals"]["total"]) == Decimal("300.0000")
        assert Decimal(result["kpi"]["total_payable"]) == Decimal("300.0000")

    def test_cashier_forbidden(
        self,
        client: TestClient,
        cashier_token: str,
    ) -> None:
        resp = client.get(
            "/api/v1/reports/ap-aging",
            headers=auth(cashier_token),
        )
        assert resp.status_code == 403
