"""Tests for Fiscal Year Close (Module: Fiscal Close)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    AccountType,
    AuditLog,
    JournalEntry,
    TransactionSplit,
)
from backend.app.models.fiscal import FiscalClose
from backend.app.services.fiscal_close import (
    assert_period_open,
    is_year_closed,
    perform_fiscal_close,
)
from backend.tests.conftest import auth


# ─── Helpers ────────────────────────────────────────────────────────────────


def _create_journal(
    db: Session,
    user_id: object,
    description: str,
    splits: list[tuple[object, Decimal, Decimal]],
    entry_date: datetime | None = None,
    reference: str | None = None,
) -> JournalEntry:
    """Create a journal entry with splits. Each split: (account_id, debit, credit)."""
    je = JournalEntry(
        entry_date=entry_date or datetime.now(timezone.utc),
        description=description,
        reference=reference,
        created_by=user_id,
    )
    db.add(je)
    db.flush()
    for account_id, debit, credit in splits:
        db.add(TransactionSplit(
            journal_entry_id=je.id,
            account_id=account_id,
            debit_amount=debit,
            credit_amount=credit,
        ))
    db.flush()
    return je


# ─── Service Tests ──────────────────────────────────────────────────────────


class TestFiscalCloseService:
    def test_close_with_profit(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        """Close a year with revenue > expenses → Retained Earnings credited."""
        sales = seed_accounts["4000"]
        cogs = seed_accounts["5000"]
        cash = seed_accounts["1000"]
        re_acct = seed_accounts["3000"]

        # Create a sale in 2025: $1000 revenue, $600 COGS
        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("1000"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("1000"))],
            entry_date=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )
        _create_journal(
            db, admin_user.id, "COGS",
            [(cogs.id, Decimal("600"), Decimal("0")),
             (cash.id, Decimal("0"), Decimal("600"))],
            entry_date=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )

        fc = perform_fiscal_close(db, fiscal_year=2025, admin_id=admin_user.id)
        db.flush()

        assert fc.fiscal_year == 2025
        assert fc.close_date.year == 2025
        assert fc.closing_entry_id is not None

        # Verify closing journal entry
        closing_je = db.query(JournalEntry).filter(
            JournalEntry.id == fc.closing_entry_id
        ).first()
        assert closing_je is not None
        assert closing_je.reference == "CLOSE-2025"

        # Verify splits balance
        splits = db.query(TransactionSplit).filter(
            TransactionSplit.journal_entry_id == closing_je.id
        ).all()
        total_debit = sum(s.debit_amount for s in splits)
        total_credit = sum(s.credit_amount for s in splits)
        assert total_debit == total_credit

        # Revenue (4000) should be debited 1000
        rev_split = [s for s in splits if s.account_id == sales.id]
        assert len(rev_split) == 1
        assert rev_split[0].debit_amount == Decimal("1000")

        # COGS (5000) should be credited 600
        exp_split = [s for s in splits if s.account_id == cogs.id]
        assert len(exp_split) == 1
        assert exp_split[0].credit_amount == Decimal("600")

        # Retained Earnings credited net income (1000 - 600 = 400)
        re_split = [s for s in splits if s.account_id == re_acct.id]
        assert len(re_split) == 1
        assert re_split[0].credit_amount == Decimal("400")

    def test_close_with_loss(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        """Close a year with expenses > revenue → Retained Earnings debited."""
        sales = seed_accounts["4000"]
        cogs = seed_accounts["5000"]
        cash = seed_accounts["1000"]
        re_acct = seed_accounts["3000"]

        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("500"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("500"))],
            entry_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
        )
        _create_journal(
            db, admin_user.id, "COGS",
            [(cogs.id, Decimal("800"), Decimal("0")),
             (cash.id, Decimal("0"), Decimal("800"))],
            entry_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
        )

        fc = perform_fiscal_close(db, fiscal_year=2025, admin_id=admin_user.id)
        db.flush()

        splits = db.query(TransactionSplit).filter(
            TransactionSplit.journal_entry_id == fc.closing_entry_id
        ).all()
        re_split = [s for s in splits if s.account_id == re_acct.id]
        assert len(re_split) == 1
        assert re_split[0].debit_amount == Decimal("300")  # 800 - 500 = 300 loss

    def test_cannot_close_current_year(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        from datetime import date
        current_year = date.today().year
        with pytest.raises(ValueError, match="Only past years"):
            perform_fiscal_close(db, fiscal_year=current_year, admin_id=admin_user.id)

    def test_cannot_close_future_year(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        from datetime import date
        with pytest.raises(ValueError, match="Only past years"):
            perform_fiscal_close(db, fiscal_year=date.today().year + 1, admin_id=admin_user.id)

    def test_cannot_close_twice(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("100"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("100"))],
            entry_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        perform_fiscal_close(db, fiscal_year=2025, admin_id=admin_user.id)
        db.flush()

        with pytest.raises(ValueError, match="already closed"):
            perform_fiscal_close(db, fiscal_year=2025, admin_id=admin_user.id)

    def test_cannot_close_empty_year(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        with pytest.raises(ValueError, match="No revenue or expense"):
            perform_fiscal_close(db, fiscal_year=2020, admin_id=admin_user.id)

    def test_closing_entry_is_balanced(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        cogs = seed_accounts["5000"]

        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("5000"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("5000"))],
            entry_date=datetime(2025, 7, 1, tzinfo=timezone.utc),
        )
        _create_journal(
            db, admin_user.id, "COGS",
            [(cogs.id, Decimal("3000"), Decimal("0")),
             (cash.id, Decimal("0"), Decimal("3000"))],
            entry_date=datetime(2025, 7, 1, tzinfo=timezone.utc),
        )

        fc = perform_fiscal_close(db, fiscal_year=2025, admin_id=admin_user.id)
        db.flush()

        splits = db.query(TransactionSplit).filter(
            TransactionSplit.journal_entry_id == fc.closing_entry_id
        ).all()
        total_d = sum(s.debit_amount for s in splits)
        total_c = sum(s.credit_amount for s in splits)
        assert total_d == total_c, f"Debits {total_d} != Credits {total_c}"


class TestPeriodLock:
    def test_is_year_closed(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("100"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("100"))],
            entry_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        assert not is_year_closed(db, 2025)
        perform_fiscal_close(db, fiscal_year=2025, admin_id=admin_user.id)
        db.flush()
        assert is_year_closed(db, 2025)

    def test_assert_period_open_passes_for_open_year(self, db: Session) -> None:
        assert_period_open(db, datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_assert_period_open_raises_for_closed_year(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("100"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("100"))],
            entry_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        perform_fiscal_close(db, fiscal_year=2025, admin_id=admin_user.id)
        db.flush()

        with pytest.raises(ValueError, match="closed"):
            assert_period_open(db, datetime(2025, 6, 15, tzinfo=timezone.utc))

    def test_audit_log_created(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("200"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("200"))],
            entry_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
        )
        perform_fiscal_close(db, fiscal_year=2025, admin_id=admin_user.id)
        db.flush()

        log = db.query(AuditLog).filter(
            AuditLog.action == "FISCAL_YEAR_CLOSED"
        ).first()
        assert log is not None
        assert log.new_values["fiscal_year"] == 2025


# ─── API Tests ──────────────────────────────────────────────────────────────


class TestFiscalCloseAPI:
    def test_list_empty(
        self, client: TestClient, admin_token: str,
    ) -> None:
        resp = client.get("/api/v1/fiscal-close", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_close_via_api(
        self,
        client: TestClient,
        admin_token: str,
        admin_user: object,
        db: Session,
        seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("1000"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("1000"))],
            entry_date=datetime(2025, 8, 1, tzinfo=timezone.utc),
        )

        resp = client.post(
            "/api/v1/fiscal-close",
            json={"fiscal_year": 2025, "notes": "Year-end close"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["fiscal_year"] == 2025
        assert data["notes"] == "Year-end close"

    def test_close_twice_returns_400(
        self,
        client: TestClient,
        admin_token: str,
        admin_user: object,
        db: Session,
        seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("100"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("100"))],
            entry_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        client.post(
            "/api/v1/fiscal-close",
            json={"fiscal_year": 2025},
            headers=auth(admin_token),
        )
        resp = client.post(
            "/api/v1/fiscal-close",
            json={"fiscal_year": 2025},
            headers=auth(admin_token),
        )
        assert resp.status_code == 400

    def test_close_current_year_returns_400(
        self, client: TestClient, admin_token: str,
    ) -> None:
        from datetime import date
        resp = client.post(
            "/api/v1/fiscal-close",
            json={"fiscal_year": date.today().year},
            headers=auth(admin_token),
        )
        assert resp.status_code == 400

    def test_cashier_cannot_close(
        self, client: TestClient, cashier_token: str,
    ) -> None:
        resp = client.post(
            "/api/v1/fiscal-close",
            json={"fiscal_year": 2025},
            headers=auth(cashier_token),
        )
        assert resp.status_code == 403

    def test_accountant_cannot_close(
        self, client: TestClient, accountant_token: str,
    ) -> None:
        resp = client.post(
            "/api/v1/fiscal-close",
            json={"fiscal_year": 2025},
            headers=auth(accountant_token),
        )
        assert resp.status_code == 403

    def test_list_after_close(
        self,
        client: TestClient,
        admin_token: str,
        admin_user: object,
        db: Session,
        seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        _create_journal(
            db, admin_user.id, "Sale",
            [(cash.id, Decimal("100"), Decimal("0")),
             (sales.id, Decimal("0"), Decimal("100"))],
            entry_date=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        client.post(
            "/api/v1/fiscal-close",
            json={"fiscal_year": 2025},
            headers=auth(admin_token),
        )
        resp = client.get("/api/v1/fiscal-close", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["fiscal_year"] == 2025
