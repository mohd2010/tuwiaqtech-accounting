"""Tests for credit invoice creation and payment recording."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    JournalEntry,
    TransactionSplit,
    User,
)
from backend.app.models.customer import Customer
from backend.app.models.inventory import Product
from backend.app.models.invoice import CreditInvoice, InvoiceStatus
from backend.app.services.credit_invoice import (
    create_credit_invoice,
    record_invoice_payment,
)
from backend.tests.conftest import auth

ZERO = Decimal("0")


# ─── Service-level tests ─────────────────────────────────────────────────────


class TestCreditInvoiceCreation:
    def test_basic_creation(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        result = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 2}],
            user_id=admin_user.id,
        )

        assert result["invoice_number"].startswith("CINV-")
        assert result["customer_name"] == "Test B2B Customer"
        assert result["status"] == "OPEN"
        # 2 * 100.0000 = 200.0000
        assert Decimal(result["total_amount"]) == Decimal("200.0000")

    def test_invoice_number_format(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        result = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 1}],
            user_id=admin_user.id,
        )
        # Format: CINV-YYYY-NNNN
        parts = result["invoice_number"].split("-")
        assert parts[0] == "CINV"
        assert len(parts[1]) == 4  # year
        assert len(parts[2]) == 4  # padded number

    def test_due_date_calculation(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        result = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 1}],
            user_id=admin_user.id,
        )
        # Customer has 30-day terms
        inv_date = result["invoice_date"]
        due_date = result["due_date"]
        assert inv_date != due_date

    def test_credit_limit_enforcement(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer_with_limit: Customer,
        product_a: Product,
    ) -> None:
        """Exceeding credit limit raises ValueError."""
        # customer_with_limit has credit_limit=500, product_a unit_price=100
        # 6 * 100 = 600 > 500
        with pytest.raises(ValueError, match="Credit limit exceeded"):
            create_credit_invoice(
                db,
                customer_id=customer_with_limit.id,
                items=[{"product_id": product_a.id, "quantity": 6}],
                user_id=admin_user.id,
            )

    def test_credit_limit_null_unlimited(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        """No credit limit means unlimited credit."""
        assert customer.credit_limit is None
        result = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 40}],
            user_id=admin_user.id,
        )
        assert Decimal(result["total_amount"]) == Decimal("4000.0000")

    def test_multi_item_invoice(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
        product_b: Product,
    ) -> None:
        result = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[
                {"product_id": product_a.id, "quantity": 2},
                {"product_id": product_b.id, "quantity": 1},
            ],
            user_id=admin_user.id,
        )
        # 2*100 + 1*200 = 400
        assert Decimal(result["total_amount"]) == Decimal("400.0000")
        assert len(result["items"]) == 2

    def test_stock_deduction(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        initial_stock = product_a.current_stock
        create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 3}],
            user_id=admin_user.id,
        )
        assert product_a.current_stock == initial_stock - 3

    def test_insufficient_stock_rejected(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        with pytest.raises(ValueError, match="Insufficient stock"):
            create_credit_invoice(
                db,
                customer_id=customer.id,
                items=[{"product_id": product_a.id, "quantity": 999}],
                user_id=admin_user.id,
            )

    def test_balanced_journal_entry(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        """Journal entry must have sum(debits) == sum(credits)."""
        result = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 2}],
            user_id=admin_user.id,
        )
        je_id = UUID(result["journal_entry_id"])
        splits = db.query(TransactionSplit).filter(
            TransactionSplit.journal_entry_id == je_id
        ).all()

        total_debit = sum(Decimal(str(s.debit_amount)) for s in splits)
        total_credit = sum(Decimal(str(s.credit_amount)) for s in splits)
        assert total_debit == total_credit


class TestInvoicePayment:
    def _create_invoice(
        self,
        db: Session,
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> dict:
        return create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 2}],
            user_id=admin_user.id,
        )

    def test_full_payment(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        inv = self._create_invoice(db, admin_user, customer, product_a)
        result = record_invoice_payment(
            db,
            invoice_id=UUID(inv["id"]),
            amount=Decimal("200.0000"),
            payment_method="CASH",
            user_id=admin_user.id,
        )
        assert result["status"] == "PAID"
        assert Decimal(result["remaining"]) == ZERO

    def test_partial_payment(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        inv = self._create_invoice(db, admin_user, customer, product_a)
        result = record_invoice_payment(
            db,
            invoice_id=UUID(inv["id"]),
            amount=Decimal("50.0000"),
            payment_method="CASH",
            user_id=admin_user.id,
        )
        assert result["status"] == "PARTIAL"
        assert Decimal(result["remaining"]) == Decimal("150.0000")

    def test_multiple_partial_payments(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        inv = self._create_invoice(db, admin_user, customer, product_a)
        inv_id = UUID(inv["id"])

        record_invoice_payment(
            db, invoice_id=inv_id, amount=Decimal("80.0000"),
            payment_method="CASH", user_id=admin_user.id,
        )
        result = record_invoice_payment(
            db, invoice_id=inv_id, amount=Decimal("120.0000"),
            payment_method="CARD", user_id=admin_user.id,
        )
        assert result["status"] == "PAID"
        assert Decimal(result["remaining"]) == ZERO

    def test_overpayment_rejected(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        inv = self._create_invoice(db, admin_user, customer, product_a)
        with pytest.raises(ValueError, match="exceeds remaining balance"):
            record_invoice_payment(
                db,
                invoice_id=UUID(inv["id"]),
                amount=Decimal("999.0000"),
                payment_method="CASH",
                user_id=admin_user.id,
            )

    def test_payment_on_paid_invoice_rejected(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        inv = self._create_invoice(db, admin_user, customer, product_a)
        inv_id = UUID(inv["id"])
        record_invoice_payment(
            db, invoice_id=inv_id, amount=Decimal("200.0000"),
            payment_method="CASH", user_id=admin_user.id,
        )
        with pytest.raises(ValueError, match="already fully paid"):
            record_invoice_payment(
                db, invoice_id=inv_id, amount=Decimal("10.0000"),
                payment_method="CASH", user_id=admin_user.id,
            )

    def test_payment_balanced_journal_entry(
        self,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        customer: Customer,
        product_a: Product,
    ) -> None:
        inv = self._create_invoice(db, admin_user, customer, product_a)
        result = record_invoice_payment(
            db,
            invoice_id=UUID(inv["id"]),
            amount=Decimal("100.0000"),
            payment_method="CASH",
            user_id=admin_user.id,
        )
        je_id = UUID(result["journal_entry_id"])
        splits = db.query(TransactionSplit).filter(
            TransactionSplit.journal_entry_id == je_id
        ).all()

        total_debit = sum(Decimal(str(s.debit_amount)) for s in splits)
        total_credit = sum(Decimal(str(s.credit_amount)) for s in splits)
        assert total_debit == total_credit


class TestInvoiceEndpoints:
    def test_list_invoices(
        self,
        client: TestClient,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        admin_token: str,
        customer: Customer,
        product_a: Product,
    ) -> None:
        create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 1}],
            user_id=admin_user.id,
        )
        resp = client.get("/api/v1/invoices/", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_cashier_forbidden(
        self,
        client: TestClient,
        cashier_token: str,
    ) -> None:
        resp = client.get("/api/v1/invoices/", headers=auth(cashier_token))
        assert resp.status_code == 403

    def test_create_via_api(
        self,
        client: TestClient,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_token: str,
        customer: Customer,
        product_a: Product,
    ) -> None:
        resp = client.post(
            "/api/v1/invoices/credit",
            headers=auth(admin_token),
            json={
                "customer_id": str(customer.id),
                "items": [
                    {"product_id": str(product_a.id), "quantity": 1},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["invoice_number"].startswith("CINV-")
        assert data["status"] == "OPEN"

    def test_get_detail(
        self,
        client: TestClient,
        db: Session,
        seed_accounts: dict[str, Account],
        admin_user: User,
        admin_token: str,
        customer: Customer,
        product_a: Product,
    ) -> None:
        inv = create_credit_invoice(
            db,
            customer_id=customer.id,
            items=[{"product_id": product_a.id, "quantity": 1}],
            user_id=admin_user.id,
        )
        resp = client.get(
            f"/api/v1/invoices/{inv['id']}",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["invoice_number"] == inv["invoice_number"]
        assert "payments" in data
