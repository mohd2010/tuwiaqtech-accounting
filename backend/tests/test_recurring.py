"""Tests for Recurring Journal Entry Templates."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, AuditLog, JournalEntry
from backend.app.models.recurring import RecurringEntry, RecurringFrequency, RecurringStatus
from backend.app.services.recurring import (
    _add_months,
    _advance_date,
    create_recurring_entry,
    delete_recurring_entry,
    get_recurring_entry,
    list_recurring_entries,
    post_recurring_entry,
    update_recurring_entry,
    update_recurring_status,
)
from backend.tests.conftest import auth


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_splits(cash_id: object, sales_id: object, amount: str = "1000") -> list[dict]:
    return [
        {"account_id": cash_id, "amount": amount, "type": "debit"},
        {"account_id": sales_id, "amount": amount, "type": "credit"},
    ]


# ─── Date Helper Tests ───────────────────────────────────────────────────────


class TestDateHelpers:
    def test_add_months_normal(self) -> None:
        assert _add_months(date(2026, 1, 15), 1) == date(2026, 2, 15)

    def test_add_months_end_of_month(self) -> None:
        # Jan 31 + 1 month = Feb 28 (non-leap year)
        assert _add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)

    def test_add_months_leap_year(self) -> None:
        # Jan 31 + 1 month in 2024 (leap year) = Feb 29
        assert _add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)

    def test_add_months_quarterly(self) -> None:
        assert _add_months(date(2026, 1, 15), 3) == date(2026, 4, 15)

    def test_add_months_annually(self) -> None:
        assert _add_months(date(2026, 2, 28), 12) == date(2027, 2, 28)

    def test_advance_date_daily(self) -> None:
        assert _advance_date(date(2026, 1, 1), RecurringFrequency.DAILY) == date(2026, 1, 2)

    def test_advance_date_weekly(self) -> None:
        assert _advance_date(date(2026, 1, 1), RecurringFrequency.WEEKLY) == date(2026, 1, 8)

    def test_advance_date_monthly(self) -> None:
        assert _advance_date(date(2026, 1, 31), RecurringFrequency.MONTHLY) == date(2026, 2, 28)

    def test_advance_date_quarterly(self) -> None:
        assert _advance_date(date(2026, 1, 15), RecurringFrequency.QUARTERLY) == date(2026, 4, 15)

    def test_advance_date_annually(self) -> None:
        assert _advance_date(date(2026, 3, 1), RecurringFrequency.ANNUALLY) == date(2027, 3, 1)


# ─── Service Tests ───────────────────────────────────────────────────────────


class TestRecurringService:
    def test_create(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        entry = create_recurring_entry(
            db,
            name="Monthly Rent",
            description="Office rent payment",
            reference_prefix="RENT",
            frequency="MONTHLY",
            next_run_date=date(2026, 3, 1),
            end_date=None,
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()

        assert entry.name == "Monthly Rent"
        assert entry.frequency == RecurringFrequency.MONTHLY
        assert entry.status == RecurringStatus.ACTIVE
        assert len(entry.splits) == 2

    def test_create_unbalanced_raises(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        with pytest.raises(ValueError, match="Double-entry"):
            create_recurring_entry(
                db,
                name="Bad",
                description="Unbalanced",
                reference_prefix=None,
                frequency="MONTHLY",
                next_run_date=date(2026, 3, 1),
                end_date=None,
                splits=[
                    {"account_id": cash.id, "amount": "1000", "type": "debit"},
                    {"account_id": sales.id, "amount": "500", "type": "credit"},
                ],
                user_id=admin_user.id,
            )

    def test_list(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        create_recurring_entry(
            db,
            name="Entry A",
            description="desc",
            reference_prefix=None,
            frequency="MONTHLY",
            next_run_date=date(2026, 1, 1),
            end_date=None,
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()
        entries = list_recurring_entries(db)
        assert len(entries) >= 1
        assert entries[0]["name"] == "Entry A"

    def test_post_creates_journal_entry(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        entry = create_recurring_entry(
            db,
            name="Monthly",
            description="Monthly posting",
            reference_prefix="MON",
            frequency="MONTHLY",
            next_run_date=date(2026, 1, 1),  # in the past
            end_date=None,
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()

        result = post_recurring_entry(db, entry_id=entry.id, user_id=admin_user.id)
        db.flush()

        assert "journal_entry_id" in result
        assert result["total_posted"] == 1
        # next_run_date advanced by 1 month
        assert result["next_run_date"] == "2026-02-01"

        # Verify the journal entry exists
        je = db.query(JournalEntry).filter(
            JournalEntry.id == result["journal_entry_id"]
        ).first()
        assert je is not None
        assert je.reference == "MON-2026-0001"

    def test_post_advances_date(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        entry = create_recurring_entry(
            db,
            name="Weekly",
            description="Weekly posting",
            reference_prefix=None,
            frequency="WEEKLY",
            next_run_date=date(2026, 1, 1),
            end_date=None,
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()

        result = post_recurring_entry(db, entry_id=entry.id, user_id=admin_user.id)
        assert result["next_run_date"] == "2026-01-08"

    def test_post_paused_raises(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        entry = create_recurring_entry(
            db,
            name="Paused",
            description="desc",
            reference_prefix=None,
            frequency="MONTHLY",
            next_run_date=date(2026, 1, 1),
            end_date=None,
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()
        update_recurring_status(db, entry_id=entry.id, new_status="PAUSED", user_id=admin_user.id)
        db.flush()

        with pytest.raises(ValueError, match="paused"):
            post_recurring_entry(db, entry_id=entry.id, user_id=admin_user.id)

    def test_post_not_due_raises(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        entry = create_recurring_entry(
            db,
            name="Future",
            description="desc",
            reference_prefix=None,
            frequency="MONTHLY",
            next_run_date=date(2099, 12, 1),
            end_date=None,
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()

        with pytest.raises(ValueError, match="not yet due"):
            post_recurring_entry(db, entry_id=entry.id, user_id=admin_user.id)

    def test_auto_pause_after_end_date(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        entry = create_recurring_entry(
            db,
            name="Ending",
            description="desc",
            reference_prefix=None,
            frequency="MONTHLY",
            next_run_date=date(2026, 1, 1),
            end_date=date(2026, 1, 15),  # end before next run after posting
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()

        post_recurring_entry(db, entry_id=entry.id, user_id=admin_user.id)
        db.flush()

        refreshed = db.query(RecurringEntry).filter(RecurringEntry.id == entry.id).first()
        assert refreshed is not None
        assert refreshed.status == RecurringStatus.PAUSED

    def test_update(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        entry = create_recurring_entry(
            db,
            name="Original",
            description="desc",
            reference_prefix=None,
            frequency="MONTHLY",
            next_run_date=date(2026, 3, 1),
            end_date=None,
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()

        update_recurring_entry(
            db, entry_id=entry.id, user_id=admin_user.id,
            name="Updated",
            frequency="QUARTERLY",
        )
        db.flush()

        refreshed = db.query(RecurringEntry).filter(RecurringEntry.id == entry.id).first()
        assert refreshed is not None
        assert refreshed.name == "Updated"
        assert refreshed.frequency == RecurringFrequency.QUARTERLY

    def test_delete(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        entry = create_recurring_entry(
            db,
            name="ToDelete",
            description="desc",
            reference_prefix=None,
            frequency="MONTHLY",
            next_run_date=date(2026, 3, 1),
            end_date=None,
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()
        eid = entry.id

        delete_recurring_entry(db, entry_id=eid, user_id=admin_user.id)
        db.flush()

        assert db.query(RecurringEntry).filter(RecurringEntry.id == eid).first() is None

    def test_pause_resume(
        self, db: Session, admin_user: object, seed_accounts: dict[str, Account],
    ) -> None:
        cash = seed_accounts["1000"]
        sales = seed_accounts["4000"]
        entry = create_recurring_entry(
            db,
            name="Toggle",
            description="desc",
            reference_prefix=None,
            frequency="MONTHLY",
            next_run_date=date(2026, 3, 1),
            end_date=None,
            splits=_make_splits(cash.id, sales.id),
            user_id=admin_user.id,
        )
        db.flush()

        update_recurring_status(db, entry_id=entry.id, new_status="PAUSED", user_id=admin_user.id)
        db.flush()
        assert entry.status == RecurringStatus.PAUSED

        update_recurring_status(db, entry_id=entry.id, new_status="ACTIVE", user_id=admin_user.id)
        db.flush()
        assert entry.status == RecurringStatus.ACTIVE


# ─── API Tests ───────────────────────────────────────────────────────────────


class TestRecurringAPI:
    def _payload(self, seed_accounts: dict[str, Account]) -> dict:
        return {
            "name": "Monthly Rent",
            "description": "Office rent",
            "reference_prefix": "RENT",
            "frequency": "MONTHLY",
            "next_run_date": "2026-01-01",
            "splits": [
                {"account_id": str(seed_accounts["1000"].id), "amount": "1000", "type": "debit"},
                {"account_id": str(seed_accounts["4000"].id), "amount": "1000", "type": "credit"},
            ],
        }

    def test_create_via_api(
        self, client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        resp = client.post(
            "/api/v1/recurring-entries",
            json=self._payload(seed_accounts),
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Monthly Rent"
        assert data["frequency"] == "MONTHLY"
        assert len(data["splits"]) == 2

    def test_list_entries(
        self, client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        client.post(
            "/api/v1/recurring-entries",
            json=self._payload(seed_accounts),
            headers=auth(admin_token),
        )
        resp = client.get("/api/v1/recurring-entries", headers=auth(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_single(
        self, client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        create_resp = client.post(
            "/api/v1/recurring-entries",
            json=self._payload(seed_accounts),
            headers=auth(admin_token),
        )
        eid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/recurring-entries/{eid}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["id"] == eid

    def test_post_via_api(
        self, client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        create_resp = client.post(
            "/api/v1/recurring-entries",
            json=self._payload(seed_accounts),
            headers=auth(admin_token),
        )
        eid = create_resp.json()["id"]
        resp = client.post(
            f"/api/v1/recurring-entries/{eid}/post",
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "journal_entry_id" in data
        assert data["total_posted"] == 1

    def test_update_via_api(
        self, client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        create_resp = client.post(
            "/api/v1/recurring-entries",
            json=self._payload(seed_accounts),
            headers=auth(admin_token),
        )
        eid = create_resp.json()["id"]
        resp = client.put(
            f"/api/v1/recurring-entries/{eid}",
            json={"name": "Updated Rent", "frequency": "QUARTERLY"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Rent"
        assert resp.json()["frequency"] == "QUARTERLY"

    def test_patch_status(
        self, client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        create_resp = client.post(
            "/api/v1/recurring-entries",
            json=self._payload(seed_accounts),
            headers=auth(admin_token),
        )
        eid = create_resp.json()["id"]
        resp = client.patch(
            f"/api/v1/recurring-entries/{eid}/status",
            json={"status": "PAUSED"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "PAUSED"

    def test_delete_via_api(
        self, client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        create_resp = client.post(
            "/api/v1/recurring-entries",
            json=self._payload(seed_accounts),
            headers=auth(admin_token),
        )
        eid = create_resp.json()["id"]
        resp = client.delete(
            f"/api/v1/recurring-entries/{eid}",
            headers=auth(admin_token),
        )
        assert resp.status_code == 204

    def test_cashier_forbidden(
        self, client: TestClient, cashier_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        resp = client.get("/api/v1/recurring-entries", headers=auth(cashier_token))
        assert resp.status_code == 403

    def test_accountant_allowed(
        self, client: TestClient, accountant_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        resp = client.post(
            "/api/v1/recurring-entries",
            json=self._payload(seed_accounts),
            headers=auth(accountant_token),
        )
        assert resp.status_code == 201

    def test_post_not_due_returns_400(
        self, client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
    ) -> None:
        payload = self._payload(seed_accounts)
        payload["next_run_date"] = "2099-12-01"
        create_resp = client.post(
            "/api/v1/recurring-entries",
            json=payload,
            headers=auth(admin_token),
        )
        eid = create_resp.json()["id"]
        resp = client.post(
            f"/api/v1/recurring-entries/{eid}/post",
            headers=auth(admin_token),
        )
        assert resp.status_code == 400

    def test_audit_log_created(
        self, client: TestClient, admin_token: str, db: Session,
        seed_accounts: dict[str, Account],
    ) -> None:
        client.post(
            "/api/v1/recurring-entries",
            json=self._payload(seed_accounts),
            headers=auth(admin_token),
        )
        log = db.query(AuditLog).filter(
            AuditLog.action == "RECURRING_ENTRY_CREATED"
        ).first()
        assert log is not None
        assert log.new_values["name"] == "Monthly Rent"
