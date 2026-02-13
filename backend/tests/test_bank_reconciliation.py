"""Tests for bank statement entry and reconciliation."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    JournalEntry,
    TransactionSplit,
    User,
)
from backend.app.models.banking import BankStatementLine, ReconciliationStatus
from backend.app.schemas.banking import BankStatementLineCreate
from backend.app.services.bank_reconciliation import (
    auto_match,
    create_statement_lines,
    get_reconciliation_summary,
    list_statement_lines,
    list_unreconciled_splits,
    manual_match,
    reconcile_lines,
    unmatch,
)
from backend.tests.conftest import auth

ZERO = Decimal("0")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _create_bank_split(
    db: Session,
    bank_account: Account,
    user: User,
    amount: Decimal,
    entry_date: datetime | None = None,
    reference: str | None = None,
) -> TransactionSplit:
    """Create a journal entry with a debit split on the Bank account."""
    now = entry_date or datetime.now(timezone.utc)
    je = JournalEntry(
        entry_date=now,
        description="Test bank transaction",
        reference=reference,
        created_by=user.id,
    )
    db.add(je)
    db.flush()

    split = TransactionSplit(
        journal_entry_id=je.id,
        account_id=bank_account.id,
        debit_amount=amount if amount > 0 else ZERO,
        credit_amount=abs(amount) if amount < 0 else ZERO,
    )
    db.add(split)
    db.flush()
    return split


# ─── TestBankStatementEntry ──────────────────────────────────────────────────


class TestBankStatementEntry:
    def test_create_statement_lines(
        self, db: Session, admin_user: User, seed_accounts: dict[str, Account]
    ) -> None:
        """Creates UNMATCHED statement lines."""
        lines = [
            BankStatementLineCreate(
                statement_date=date(2026, 2, 1),
                description="Card payment deposit",
                amount=Decimal("500.0000"),
                reference="REF-001",
            ),
            BankStatementLineCreate(
                statement_date=date(2026, 2, 2),
                description="Wire transfer",
                amount=Decimal("1200.0000"),
            ),
        ]
        created = create_statement_lines(db, lines, admin_user.id)
        assert len(created) == 2
        assert all(bsl.status == ReconciliationStatus.UNMATCHED for bsl in created)

    def test_list_statement_lines(
        self, db: Session, admin_user: User, seed_accounts: dict[str, Account]
    ) -> None:
        """Returns all statement lines."""
        lines = [
            BankStatementLineCreate(
                statement_date=date(2026, 2, 1),
                description="Deposit",
                amount=Decimal("100.0000"),
            ),
        ]
        create_statement_lines(db, lines, admin_user.id)
        result = list_statement_lines(db)
        assert len(result) >= 1
        assert result[0]["status"] == "UNMATCHED"


# ─── TestAutoMatch ───────────────────────────────────────────────────────────


class TestAutoMatch:
    def test_auto_match_by_amount_and_date(
        self, db: Session, admin_user: User, seed_accounts: dict[str, Account]
    ) -> None:
        """Exact amount + date proximity auto-matches."""
        bank_account = seed_accounts["1200"]
        amount = Decimal("500.0000")

        # Create a bank GL split
        _create_bank_split(
            db, bank_account, admin_user, amount,
            entry_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
            reference="INV-2026-0001",
        )

        # Create a matching statement line
        create_statement_lines(
            db,
            [BankStatementLineCreate(
                statement_date=date(2026, 2, 1),
                description="Card deposit",
                amount=amount,
                reference="INV-2026-0001",
            )],
            admin_user.id,
        )

        matched = auto_match(db, admin_user.id)
        assert matched == 1

        # Verify status changed
        bsl = db.query(BankStatementLine).first()
        assert bsl is not None
        assert bsl.status == ReconciliationStatus.MATCHED
        assert bsl.matched_split_id is not None

    def test_auto_match_no_match_when_amount_differs(
        self, db: Session, admin_user: User, seed_accounts: dict[str, Account]
    ) -> None:
        """No false positive when amounts don't match."""
        bank_account = seed_accounts["1200"]

        _create_bank_split(
            db, bank_account, admin_user, Decimal("500.0000"),
            entry_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        create_statement_lines(
            db,
            [BankStatementLineCreate(
                statement_date=date(2026, 2, 1),
                description="Different amount",
                amount=Decimal("600.0000"),
            )],
            admin_user.id,
        )

        matched = auto_match(db, admin_user.id)
        assert matched == 0


# ─── TestManualMatch ─────────────────────────────────────────────────────────


class TestManualMatch:
    def test_manual_match_and_unmatch(
        self, db: Session, admin_user: User, seed_accounts: dict[str, Account]
    ) -> None:
        """Full cycle: UNMATCHED → MATCHED → UNMATCHED."""
        bank_account = seed_accounts["1200"]
        amount = Decimal("300.0000")

        split = _create_bank_split(db, bank_account, admin_user, amount)

        create_statement_lines(
            db,
            [BankStatementLineCreate(
                statement_date=date(2026, 2, 5),
                description="Manual match test",
                amount=amount,
            )],
            admin_user.id,
        )
        bsl = db.query(BankStatementLine).first()
        assert bsl is not None

        # Match
        manual_match(db, bsl.id, split.id, admin_user.id)
        db.refresh(bsl)
        assert bsl.status == ReconciliationStatus.MATCHED
        assert bsl.matched_split_id == split.id

        # Unmatch
        unmatch(db, bsl.id, admin_user.id)
        db.refresh(bsl)
        assert bsl.status == ReconciliationStatus.UNMATCHED
        assert bsl.matched_split_id is None

    def test_match_wrong_account_raises(
        self, db: Session, admin_user: User, seed_accounts: dict[str, Account]
    ) -> None:
        """Split not on Bank account is rejected."""
        cash_account = seed_accounts["1000"]

        # Create a split on Cash account (not Bank)
        je = JournalEntry(
            entry_date=datetime.now(timezone.utc),
            description="Cash test",
            created_by=admin_user.id,
        )
        db.add(je)
        db.flush()
        split = TransactionSplit(
            journal_entry_id=je.id,
            account_id=cash_account.id,
            debit_amount=Decimal("100.0000"),
            credit_amount=ZERO,
        )
        db.add(split)
        db.flush()

        create_statement_lines(
            db,
            [BankStatementLineCreate(
                statement_date=date(2026, 2, 5),
                description="Wrong account test",
                amount=Decimal("100.0000"),
            )],
            admin_user.id,
        )
        bsl = db.query(BankStatementLine).first()
        assert bsl is not None

        with pytest.raises(ValueError, match="not on the Bank account"):
            manual_match(db, bsl.id, split.id, admin_user.id)


# ─── TestReconcile ───────────────────────────────────────────────────────────


class TestReconcile:
    def test_reconcile_matched_lines(
        self, db: Session, admin_user: User, seed_accounts: dict[str, Account]
    ) -> None:
        """MATCHED → RECONCILED with timestamp."""
        bank_account = seed_accounts["1200"]
        amount = Decimal("200.0000")

        split = _create_bank_split(db, bank_account, admin_user, amount)

        create_statement_lines(
            db,
            [BankStatementLineCreate(
                statement_date=date(2026, 2, 5),
                description="Reconcile test",
                amount=amount,
            )],
            admin_user.id,
        )
        bsl = db.query(BankStatementLine).first()
        assert bsl is not None

        manual_match(db, bsl.id, split.id, admin_user.id)
        count = reconcile_lines(db, [bsl.id], admin_user.id)
        assert count == 1

        db.refresh(bsl)
        assert bsl.status == ReconciliationStatus.RECONCILED
        assert bsl.reconciled_by == admin_user.id
        assert bsl.reconciled_at is not None

    def test_cannot_reconcile_unmatched(
        self, db: Session, admin_user: User, seed_accounts: dict[str, Account]
    ) -> None:
        """ValueError for UNMATCHED lines."""
        create_statement_lines(
            db,
            [BankStatementLineCreate(
                statement_date=date(2026, 2, 5),
                description="Unmatched line",
                amount=Decimal("100.0000"),
            )],
            admin_user.id,
        )
        bsl = db.query(BankStatementLine).first()
        assert bsl is not None

        with pytest.raises(ValueError, match="not MATCHED"):
            reconcile_lines(db, [bsl.id], admin_user.id)


# ─── TestReconciliationSummary ───────────────────────────────────────────────


class TestReconciliationSummary:
    def test_summary_returns_balances(
        self, db: Session, admin_user: User, seed_accounts: dict[str, Account]
    ) -> None:
        """GL balance and counts are correct."""
        bank_account = seed_accounts["1200"]

        # Create bank GL entries
        _create_bank_split(db, bank_account, admin_user, Decimal("1000.0000"))
        _create_bank_split(db, bank_account, admin_user, Decimal("500.0000"))

        # Create statement lines
        create_statement_lines(
            db,
            [
                BankStatementLineCreate(
                    statement_date=date(2026, 2, 1),
                    description="Line 1",
                    amount=Decimal("1000.0000"),
                ),
                BankStatementLineCreate(
                    statement_date=date(2026, 2, 2),
                    description="Line 2",
                    amount=Decimal("500.0000"),
                ),
            ],
            admin_user.id,
        )

        summary = get_reconciliation_summary(db)
        assert Decimal(summary["gl_balance"]) == Decimal("1500.0000")
        assert Decimal(summary["statement_balance"]) == Decimal("1500.0000")
        assert summary["unmatched_count"] == 2
        assert summary["matched_count"] == 0
        assert summary["reconciled_count"] == 0


# ─── TestBankReconciliationAPI ───────────────────────────────────────────────


class TestBankReconciliationAPI:
    def test_add_lines_via_api(
        self,
        client,
        db: Session,
        admin_user: User,
        admin_token: str,
        seed_accounts: dict[str, Account],
    ) -> None:
        """POST /banking/statement-lines creates lines."""
        res = client.post(
            "/api/v1/banking/statement-lines",
            json={
                "lines": [
                    {
                        "statement_date": "2026-02-01",
                        "description": "Card deposit",
                        "amount": "500.0000",
                        "reference": "REF-001",
                    },
                ],
            },
            headers=auth(admin_token),
        )
        assert res.status_code == 201
        data = res.json()
        assert len(data) >= 1

    def test_auto_match_via_api(
        self,
        client,
        db: Session,
        admin_user: User,
        admin_token: str,
        seed_accounts: dict[str, Account],
    ) -> None:
        """POST /banking/auto-match returns match count."""
        res = client.post(
            "/api/v1/banking/auto-match",
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert "matched" in data

    def test_cashier_forbidden(
        self,
        client,
        db: Session,
        cashier_user: User,
        cashier_token: str,
        seed_accounts: dict[str, Account],
    ) -> None:
        """403 for cashier role on banking endpoints."""
        res = client.get(
            "/api/v1/banking/summary",
            headers=auth(cashier_token),
        )
        assert res.status_code == 403
