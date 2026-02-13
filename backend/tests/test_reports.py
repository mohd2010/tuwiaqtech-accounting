"""Tests for enhanced financial reports (Module 11)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    JournalEntry,
    TransactionSplit,
    User,
)
from backend.tests.conftest import auth

ZERO = Decimal("0")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _je(
    db: Session,
    user: User,
    entry_date: datetime,
    splits: list[tuple[Account, Decimal, Decimal]],
    reference: str | None = None,
    description: str = "Test entry",
) -> JournalEntry:
    """Create a balanced journal entry with the given splits."""
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


# ── TestDateFiltering ────────────────────────────────────────────────────────


class TestDateFiltering:
    """Existing reports now respect from_date / to_date parameters."""

    def test_income_statement_with_dates(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        # Jan sale: 115 SAR (100 revenue + 15 VAT)
        _je(db, admin_user, datetime(2026, 1, 15, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("115"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("100")),
            (seed_accounts["2200"], ZERO, Decimal("15")),
        ])
        # Feb sale: 230 SAR (200 revenue + 30 VAT)
        _je(db, admin_user, datetime(2026, 2, 10, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("230"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("200")),
            (seed_accounts["2200"], ZERO, Decimal("30")),
        ])

        res = client.get(
            "/api/v1/reports/income-statement",
            params={"from_date": "2026-01-01", "to_date": "2026-01-31"},
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert Decimal(data["revenue"]) == Decimal("100")

    def test_income_statement_defaults_to_current_month(
        self, client, admin_user, admin_token, seed_accounts,
    ):
        res = client.get(
            "/api/v1/reports/income-statement",
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert "from_date" in data
        assert "to_date" in data

    def test_trial_balance_with_dates(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        _je(db, admin_user, datetime(2026, 1, 15, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("100"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("100")),
        ])
        _je(db, admin_user, datetime(2026, 2, 10, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("200"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("200")),
        ])

        res = client.get(
            "/api/v1/reports/trial-balance",
            params={"from_date": "2026-01-01", "to_date": "2026-01-31"},
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        # Find Cash account in the response
        cash_row = next(a for a in data["accounts"] if a["account_code"] == "1000")
        assert Decimal(cash_row["debit"]) == Decimal("100")

    def test_balance_sheet_cumulative(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        # Use far-future dates to isolate from existing DB data
        _je(db, admin_user, datetime(2030, 1, 10, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("500"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("500")),
        ])
        _je(db, admin_user, datetime(2030, 2, 10, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("300"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("300")),
        ])

        # Get baseline: everything before our test entries
        res_before = client.get(
            "/api/v1/reports/balance-sheet",
            params={"as_of_date": "2029-12-31"},
            headers=auth(admin_token),
        )
        baseline = Decimal(res_before.json()["total_assets"])

        # As of Jan 31 2030 — should include baseline + 500
        res1 = client.get(
            "/api/v1/reports/balance-sheet",
            params={"as_of_date": "2030-01-31"},
            headers=auth(admin_token),
        )
        assert res1.status_code == 200
        assets_jan = Decimal(res1.json()["total_assets"])
        assert assets_jan - baseline == Decimal("500")

        # As of Feb 28 2030 — should include baseline + 800
        res2 = client.get(
            "/api/v1/reports/balance-sheet",
            params={"as_of_date": "2030-02-28"},
            headers=auth(admin_token),
        )
        assets_feb = Decimal(res2.json()["total_assets"])
        assert assets_feb - baseline == Decimal("800")


# ── TestGeneralLedger ────────────────────────────────────────────────────────


class TestGeneralLedger:

    def test_running_balance(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        _je(db, admin_user, datetime(2026, 1, 10, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("500"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("500")),
        ], reference="INV-001")
        _je(db, admin_user, datetime(2026, 1, 20, tzinfo=timezone.utc), [
            (seed_accounts["5000"], Decimal("200"), ZERO),
            (seed_accounts["1000"], ZERO, Decimal("200")),
        ], reference="EXP-001")

        res = client.get(
            "/api/v1/reports/general-ledger",
            params={"account_code": "1000", "from_date": "2026-01-01", "to_date": "2026-01-31"},
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["account_code"] == "1000"
        assert len(data["entries"]) == 2
        assert Decimal(data["opening_balance"]) == ZERO
        assert Decimal(data["entries"][0]["running_balance"]) == Decimal("500")
        assert Decimal(data["entries"][1]["running_balance"]) == Decimal("300")
        assert Decimal(data["closing_balance"]) == Decimal("300")

    def test_opening_balance(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        # Entry before the date range
        _je(db, admin_user, datetime(2025, 12, 15, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("1000"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("1000")),
        ])
        # Entry in the range
        _je(db, admin_user, datetime(2026, 1, 10, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("200"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("200")),
        ])

        res = client.get(
            "/api/v1/reports/general-ledger",
            params={"account_code": "1000", "from_date": "2026-01-01", "to_date": "2026-01-31"},
            headers=auth(admin_token),
        )
        data = res.json()
        assert Decimal(data["opening_balance"]) == Decimal("1000")
        assert len(data["entries"]) == 1
        assert Decimal(data["closing_balance"]) == Decimal("1200")

    def test_invalid_account(self, client, admin_user, admin_token, seed_accounts):
        res = client.get(
            "/api/v1/reports/general-ledger",
            params={"account_code": "9999", "from_date": "2026-01-01", "to_date": "2026-01-31"},
            headers=auth(admin_token),
        )
        assert res.status_code == 404


# ── TestVATReport ────────────────────────────────────────────────────────────


class TestVATReport:

    def test_totals(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        _je(db, admin_user, datetime(2026, 1, 15, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("115"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("100")),
            (seed_accounts["2200"], ZERO, Decimal("15")),
        ], reference="INV-2026-0001")

        res = client.get(
            "/api/v1/reports/vat-report",
            params={"from_date": "2026-01-01", "to_date": "2026-01-31"},
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert Decimal(data["total_vat_collected"]) == Decimal("15")
        assert Decimal(data["total_sales_ex_vat"]) == Decimal("100")
        assert Decimal(data["effective_vat_rate"]) == Decimal("15.00")

    def test_monthly_breakdown(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        # Jan sale
        _je(db, admin_user, datetime(2026, 1, 15, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("115"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("100")),
            (seed_accounts["2200"], ZERO, Decimal("15")),
        ])
        # Feb sale
        _je(db, admin_user, datetime(2026, 2, 10, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("230"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("200")),
            (seed_accounts["2200"], ZERO, Decimal("30")),
        ])

        res = client.get(
            "/api/v1/reports/vat-report",
            params={"from_date": "2026-01-01", "to_date": "2026-02-28"},
            headers=auth(admin_token),
        )
        data = res.json()
        assert len(data["monthly_breakdown"]) == 2
        jan = next(m for m in data["monthly_breakdown"] if m["month"] == "2026-01")
        assert Decimal(jan["vat_collected"]) == Decimal("15")


# ── TestCashFlow ─────────────────────────────────────────────────────────────


class TestCashFlow:

    def test_cash_flow_from_sale(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        _je(db, admin_user, datetime(2026, 1, 15, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("115"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("100")),
            (seed_accounts["2200"], ZERO, Decimal("15")),
        ])

        res = client.get(
            "/api/v1/reports/cash-flow",
            params={"from_date": "2026-01-01", "to_date": "2026-01-31"},
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert Decimal(data["net_change"]) == Decimal("115")
        assert Decimal(data["closing_cash_balance"]) == Decimal("115")

    def test_opening_and_closing(
        self, client, db, admin_user, admin_token, seed_accounts,
    ):
        # Entry before range
        _je(db, admin_user, datetime(2025, 12, 15, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("1000"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("1000")),
        ])
        # Entry in range
        _je(db, admin_user, datetime(2026, 1, 10, tzinfo=timezone.utc), [
            (seed_accounts["1000"], Decimal("200"), ZERO),
            (seed_accounts["4000"], ZERO, Decimal("200")),
        ])

        res = client.get(
            "/api/v1/reports/cash-flow",
            params={"from_date": "2026-01-01", "to_date": "2026-01-31"},
            headers=auth(admin_token),
        )
        data = res.json()
        assert Decimal(data["opening_cash_balance"]) == Decimal("1000")
        assert Decimal(data["net_change"]) == Decimal("200")
        assert Decimal(data["closing_cash_balance"]) == Decimal("1200")


# ── TestRoleAccess ───────────────────────────────────────────────────────────


class TestRoleAccess:

    @pytest.mark.parametrize("endpoint", [
        "/api/v1/reports/income-statement",
        "/api/v1/reports/trial-balance",
        "/api/v1/reports/balance-sheet",
        "/api/v1/reports/general-ledger?account_code=1000",
        "/api/v1/reports/vat-report",
        "/api/v1/reports/cash-flow",
    ])
    def test_cashier_forbidden(
        self, client, cashier_user, cashier_token, seed_accounts, endpoint,
    ):
        res = client.get(endpoint, headers=auth(cashier_token))
        assert res.status_code == 403

    def test_accountant_allowed(
        self, client, accountant_user, accountant_token, seed_accounts,
    ):
        res = client.get(
            "/api/v1/reports/income-statement",
            headers=auth(accountant_token),
        )
        assert res.status_code == 200
