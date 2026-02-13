"""Tests for dashboard analytics (Module 13)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    JournalEntry,
    TransactionSplit,
    User,
)
from backend.app.models.customer import Customer, Sale
from backend.app.models.inventory import Category, Product
from backend.app.models.invoice import CreditInvoice, InvoiceStatus
from backend.app.models.pos import PaymentMethod, SalePayment
from backend.tests.conftest import auth

ZERO = Decimal("0")
NOW = datetime.now(timezone.utc)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _je(
    db: Session,
    user: User,
    entry_date: datetime,
    splits: list[tuple[Account, Decimal, Decimal]],
    reference: str | None = None,
    description: str = "Test entry",
) -> JournalEntry:
    je = JournalEntry(
        entry_date=entry_date,
        description=description,
        reference=reference,
        created_by=user.id,
    )
    db.add(je)
    db.flush()
    for account, debit, credit in splits:
        db.add(TransactionSplit(
            journal_entry_id=je.id,
            account_id=account.id,
            debit_amount=debit,
            credit_amount=credit,
        ))
    db.flush()
    return je


ENDPOINT = "/api/v1/reports/dashboard-summary"


# ── Tests ────────────────────────────────────────────────────────────────────


class TestDashboardAnalytics:

    def test_response_includes_new_fields(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        res = client.get(ENDPOINT, headers=auth(admin_token))
        assert res.status_code == 200
        data = res.json()
        new_keys = [
            "gross_margin_pct", "accounts_receivable", "accounts_payable",
            "cash_position", "revenue_expense_trend", "top_products",
            "sales_by_payment_method", "cash_flow_forecast",
            "inventory_turnover", "ar_aging_summary",
        ]
        for key in new_keys:
            assert key in data, f"Missing key: {key}"

    def test_gross_margin_calculation(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        # Get baseline
        base = client.get(ENDPOINT, headers=auth(admin_token)).json()
        base_rev = Decimal(base["revenue"])
        base_cogs = Decimal(base["gross_margin_pct"])

        # Add Revenue 1000, COGS 600
        _je(db, admin_user, NOW, [
            (seed_accounts["1000"], Decimal("1000"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("1000")),
        ], description="Sale")
        _je(db, admin_user, NOW, [
            (seed_accounts["5000"], Decimal("600"), ZERO),
            (seed_accounts["1100"], ZERO, Decimal("600")),
        ], description="COGS")

        res = client.get(ENDPOINT, headers=auth(admin_token))
        assert res.status_code == 200
        data = res.json()
        margin = Decimal(data["gross_margin_pct"])
        # Margin should be positive (revenue > COGS)
        assert margin > Decimal("0")

    def test_accounts_receivable_from_credit_invoices(
        self, client, db, admin_user, admin_token, seed_accounts, customer,
    ):
        je = _je(db, admin_user, NOW, [
            (seed_accounts["1300"], Decimal("500"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("500")),
        ], description="Credit sale")

        inv = CreditInvoice(
            customer_id=customer.id,
            journal_entry_id=je.id,
            invoice_number="INV-TEST-001",
            invoice_date=NOW,
            due_date=NOW + timedelta(days=30),
            total_amount=Decimal("500"),
            amount_paid=Decimal("200"),
            status=InvoiceStatus.PARTIAL,
        )
        db.add(inv)
        db.flush()

        res = client.get(ENDPOINT, headers=auth(admin_token))
        data = res.json()
        assert Decimal(data["accounts_receivable"]) == Decimal("300")

    def test_cash_position_combines_cash_and_bank(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        # Get baseline
        base = client.get(ENDPOINT, headers=auth(admin_token)).json()
        base_pos = Decimal(base["cash_position"])

        # Cash 1000, Bank 2000
        _je(db, admin_user, NOW, [
            (seed_accounts["1000"], Decimal("1000"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("1000")),
        ], description="Cash sale")
        _je(db, admin_user, NOW, [
            (seed_accounts["1200"], Decimal("2000"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("2000")),
        ], description="Bank sale")

        res = client.get(ENDPOINT, headers=auth(admin_token))
        data = res.json()
        new_pos = Decimal(data["cash_position"])
        assert new_pos - base_pos == Decimal("3000")

    def test_top_products_returns_max_5(
        self, client, db, admin_user, admin_token, seed_accounts, category,
    ):
        products = []
        for i in range(6):
            p = Product(
                name=f"Prod-{i}",
                sku=f"TP-{i}",
                category_id=category.id,
                unit_price=Decimal("10"),
                cost_price=Decimal("5"),
                current_stock=100,
                reorder_level=10,
            )
            db.add(p)
            products.append(p)
        db.flush()

        je = _je(db, admin_user, NOW, [
            (seed_accounts["1000"], Decimal("600"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("600")),
        ], description="Sales")

        for i, p in enumerate(products):
            sale = Sale(
                journal_entry_id=je.id,
                product_id=p.id,
                quantity=1,
                total_amount=Decimal(str((i + 1) * 100)),
            )
            db.add(sale)
        db.flush()

        res = client.get(ENDPOINT, headers=auth(admin_token))
        data = res.json()
        assert len(data["top_products"]) == 5

    def test_sales_by_payment_method(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        je = _je(db, admin_user, NOW, [
            (seed_accounts["1000"], Decimal("300"), ZERO),
            (seed_accounts["1200"], Decimal("500"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("800")),
        ], description="Mixed payment sale")

        cash_pay = SalePayment(
            journal_entry_id=je.id,
            payment_method=PaymentMethod.CASH,
            account_id=seed_accounts["1000"].id,
            amount=Decimal("300"),
        )
        card_pay = SalePayment(
            journal_entry_id=je.id,
            payment_method=PaymentMethod.CARD,
            account_id=seed_accounts["1200"].id,
            amount=Decimal("500"),
        )
        db.add_all([cash_pay, card_pay])
        db.flush()

        res = client.get(ENDPOINT, headers=auth(admin_token))
        data = res.json()
        methods = {m["method"]: Decimal(m["total"]) for m in data["sales_by_payment_method"]}
        assert methods["CASH"] == Decimal("300")
        assert methods["CARD"] == Decimal("500")

    def test_ar_aging_summary_buckets(
        self, client, db, admin_user, admin_token, seed_accounts, customer,
    ):
        je = _je(db, admin_user, NOW, [
            (seed_accounts["1300"], Decimal("1000"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("1000")),
        ], description="Credit sale")

        inv = CreditInvoice(
            customer_id=customer.id,
            journal_entry_id=je.id,
            invoice_number="INV-AGING-001",
            invoice_date=NOW - timedelta(days=45),
            due_date=NOW - timedelta(days=15),
            total_amount=Decimal("1000"),
            amount_paid=ZERO,
            status=InvoiceStatus.OPEN,
        )
        db.add(inv)
        db.flush()

        res = client.get(ENDPOINT, headers=auth(admin_token))
        data = res.json()
        aging = data["ar_aging_summary"]
        assert "current" in aging
        assert "days_31_60" in aging
        assert "days_61_90" in aging
        assert "over_90" in aging
        # 15 days overdue → current bucket
        assert Decimal(aging["current"]) == Decimal("1000")

    def test_cashier_can_access(
        self, client, db, cashier_user, cashier_token, seed_accounts,
    ):
        res = client.get(ENDPOINT, headers=auth(cashier_token))
        assert res.status_code == 200
