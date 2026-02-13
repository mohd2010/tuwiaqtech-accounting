"""Tests for user management endpoints (Module 15)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.accounting import AuditLog, User
from backend.tests.conftest import auth


class TestListUsers:
    def test_admin_can_list_users(
        self, client: TestClient, admin_token: str, admin_user: User
    ) -> None:
        resp = client.get("/api/v1/users", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(u["id"] == str(admin_user.id) for u in data)

    def test_accountant_cannot_list_users(
        self, client: TestClient, accountant_token: str
    ) -> None:
        resp = client.get("/api/v1/users", headers=auth(accountant_token))
        assert resp.status_code == 403

    def test_cashier_cannot_list_users(
        self, client: TestClient, cashier_token: str
    ) -> None:
        resp = client.get("/api/v1/users", headers=auth(cashier_token))
        assert resp.status_code == 403


class TestCreateUser:
    def test_admin_creates_user(
        self, client: TestClient, admin_token: str, db: Session
    ) -> None:
        resp = client.post(
            "/api/v1/users",
            json={"username": "new_employee", "password": "Secret123!@#x", "role": "CASHIER"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "new_employee"
        assert data["role"] == "CASHIER"
        assert data["is_active"] is True

    def test_duplicate_username_returns_409(
        self, client: TestClient, admin_token: str, admin_user: User
    ) -> None:
        resp = client.post(
            "/api/v1/users",
            json={"username": "test_admin", "password": "Secret123!@#x", "role": "CASHIER"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 409

    def test_duplicate_username_case_insensitive(
        self, client: TestClient, admin_token: str, admin_user: User
    ) -> None:
        resp = client.post(
            "/api/v1/users",
            json={"username": "TEST_ADMIN", "password": "Secret123!@#x", "role": "CASHIER"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 409

    def test_short_username_rejected(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.post(
            "/api/v1/users",
            json={"username": "ab", "password": "Secret123!@#x", "role": "CASHIER"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    def test_short_password_rejected(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.post(
            "/api/v1/users",
            json={"username": "validuser", "password": "short", "role": "CASHIER"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    def test_create_user_audit_logged(
        self, client: TestClient, admin_token: str, db: Session
    ) -> None:
        client.post(
            "/api/v1/users",
            json={"username": "audited_user", "password": "Secret123!@#x", "role": "ACCOUNTANT"},
            headers=auth(admin_token),
        )
        log = (
            db.query(AuditLog)
            .filter(AuditLog.action == "USER_CREATED")
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        assert log is not None
        assert log.new_values["username"] == "audited_user"
        assert log.new_values["role"] == "ACCOUNTANT"

    def test_cashier_cannot_create_user(
        self, client: TestClient, cashier_token: str
    ) -> None:
        resp = client.post(
            "/api/v1/users",
            json={"username": "sneaky", "password": "Secret123!@#x", "role": "ADMIN"},
            headers=auth(cashier_token),
        )
        assert resp.status_code == 403


class TestUpdateUser:
    def test_admin_updates_username(
        self, client: TestClient, admin_token: str, cashier_user: User
    ) -> None:
        resp = client.patch(
            f"/api/v1/users/{cashier_user.id}",
            json={"username": "renamed_cashier"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "renamed_cashier"

    def test_admin_updates_role(
        self, client: TestClient, admin_token: str, cashier_user: User
    ) -> None:
        resp = client.patch(
            f"/api/v1/users/{cashier_user.id}",
            json={"role": "ACCOUNTANT"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "ACCOUNTANT"

    def test_update_nonexistent_user_returns_404(
        self, client: TestClient, admin_token: str
    ) -> None:
        fake_id = str(uuid4())
        resp = client.patch(
            f"/api/v1/users/{fake_id}",
            json={"username": "ghost"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 404

    def test_update_duplicate_username_returns_409(
        self,
        client: TestClient,
        admin_token: str,
        cashier_user: User,
        accountant_user: User,
    ) -> None:
        resp = client.patch(
            f"/api/v1/users/{cashier_user.id}",
            json={"username": "test_accountant"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 409


class TestToggleActive:
    def test_admin_deactivates_user(
        self, client: TestClient, admin_token: str, cashier_user: User
    ) -> None:
        resp = client.patch(
            f"/api/v1/users/{cashier_user.id}/toggle-active",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_admin_reactivates_user(
        self, client: TestClient, admin_token: str, cashier_user: User, db: Session
    ) -> None:
        cashier_user.is_active = False
        db.flush()
        resp = client.patch(
            f"/api/v1/users/{cashier_user.id}/toggle-active",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    def test_admin_cannot_deactivate_self(
        self, client: TestClient, admin_token: str, admin_user: User
    ) -> None:
        resp = client.patch(
            f"/api/v1/users/{admin_user.id}/toggle-active",
            headers=auth(admin_token),
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()

    def test_toggle_nonexistent_returns_404(
        self, client: TestClient, admin_token: str
    ) -> None:
        fake_id = str(uuid4())
        resp = client.patch(
            f"/api/v1/users/{fake_id}/toggle-active",
            headers=auth(admin_token),
        )
        assert resp.status_code == 404


class TestResetPassword:
    def test_admin_resets_password(
        self, client: TestClient, admin_token: str, cashier_user: User
    ) -> None:
        resp = client.post(
            f"/api/v1/users/{cashier_user.id}/reset-password",
            json={"new_password": "NewPass123!@#"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert "reset" in resp.json()["detail"].lower()

    def test_reset_password_audit_logged(
        self, client: TestClient, admin_token: str, cashier_user: User, db: Session
    ) -> None:
        client.post(
            f"/api/v1/users/{cashier_user.id}/reset-password",
            json={"new_password": "NewPass123!@#"},
            headers=auth(admin_token),
        )
        log = (
            db.query(AuditLog)
            .filter(AuditLog.action == "USER_PASSWORD_RESET")
            .first()
        )
        assert log is not None

    def test_reset_nonexistent_returns_404(
        self, client: TestClient, admin_token: str
    ) -> None:
        fake_id = str(uuid4())
        resp = client.post(
            f"/api/v1/users/{fake_id}/reset-password",
            json={"new_password": "NewPass123!@#"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 404


class TestChangeOwnPassword:
    def test_user_changes_own_password(
        self, client: TestClient, cashier_token: str
    ) -> None:
        resp = client.post(
            "/api/v1/users/change-password",
            json={"current_password": "pass", "new_password": "NewPass123!@#"},
            headers=auth(cashier_token),
        )
        assert resp.status_code == 200
        assert "changed" in resp.json()["detail"].lower()

    def test_wrong_current_password_returns_400(
        self, client: TestClient, cashier_token: str
    ) -> None:
        resp = client.post(
            "/api/v1/users/change-password",
            json={"current_password": "wrongpass", "new_password": "NewPass123!@#"},
            headers=auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    def test_change_password_audit_logged(
        self, client: TestClient, cashier_token: str, db: Session
    ) -> None:
        client.post(
            "/api/v1/users/change-password",
            json={"current_password": "pass", "new_password": "NewPass123!@#"},
            headers=auth(cashier_token),
        )
        log = (
            db.query(AuditLog)
            .filter(AuditLog.action == "USER_PASSWORD_CHANGED")
            .first()
        )
        assert log is not None


class TestGetMe:
    def test_get_current_user(
        self, client: TestClient, admin_token: str, admin_user: User
    ) -> None:
        resp = client.get("/api/v1/users/me", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["username"] == "test_admin"
        assert resp.json()["role"] == "ADMIN"

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401
