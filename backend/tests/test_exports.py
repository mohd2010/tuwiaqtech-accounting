"""Tests for report export endpoints (Excel + PDF)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, AuditLog
from backend.tests.conftest import auth


# ── Excel exports ────────────────────────────────────────────────────────


def test_income_statement_excel_returns_xlsx(
    client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
) -> None:
    resp = client.get(
        "/api/v1/reports/income-statement/export/excel",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    # XLSX files are ZIP archives starting with PK
    assert resp.content[:2] == b"PK"


def test_income_statement_pdf_returns_pdf(
    client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
) -> None:
    resp = client.get(
        "/api/v1/reports/income-statement/export/pdf",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


def test_trial_balance_excel_returns_xlsx(
    client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
) -> None:
    resp = client.get(
        "/api/v1/reports/trial-balance/export/excel",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert resp.content[:2] == b"PK"


def test_balance_sheet_pdf_returns_pdf(
    client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
) -> None:
    resp = client.get(
        "/api/v1/reports/balance-sheet/export/pdf",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


# ── Role checks ──────────────────────────────────────────────────────────


def test_cashier_cannot_export(
    client: TestClient, cashier_token: str, seed_accounts: dict[str, Account],
) -> None:
    resp = client.get(
        "/api/v1/reports/income-statement/export/excel",
        headers=auth(cashier_token),
    )
    assert resp.status_code == 403


def test_accountant_can_export(
    client: TestClient, accountant_token: str, seed_accounts: dict[str, Account],
) -> None:
    resp = client.get(
        "/api/v1/reports/trial-balance/export/pdf",
        headers=auth(accountant_token),
    )
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


# ── Audit logging ────────────────────────────────────────────────────────


def test_export_audit_logged(
    client: TestClient, admin_token: str, db: Session,
    seed_accounts: dict[str, Account],
) -> None:
    resp = client.get(
        "/api/v1/reports/vat-report/export/excel",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200

    log = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "REPORT_EXPORTED",
            AuditLog.record_id == "vat-report",
        )
        .first()
    )
    assert log is not None
    assert log.new_values["format"] == "excel"


# ── Validation ───────────────────────────────────────────────────────────


def test_general_ledger_export_requires_account_code(
    client: TestClient, admin_token: str, seed_accounts: dict[str, Account],
) -> None:
    resp = client.get(
        "/api/v1/reports/general-ledger/export/excel",
        headers=auth(admin_token),
    )
    assert resp.status_code == 422
