"""Tests for warehouse CRUD — service layer + API endpoints."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import AuditLog, User
from backend.app.models.inventory import Warehouse
from backend.app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from backend.app.services.warehouse import (
    create_warehouse,
    get_warehouse_stock,
    list_warehouses,
    update_warehouse,
)
from backend.tests.conftest import auth


# ═══════════════════════════════════════════════════════════════════════════════
#  Service-layer tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWarehouseService:
    def test_create_warehouse(self, db: Session, admin_user: User) -> None:
        data = WarehouseCreate(name="Warehouse X", address="123 Main St")
        result = create_warehouse(db, data, admin_user.id)
        assert result.name == "Warehouse X"
        assert result.address == "123 Main St"
        assert result.is_active is True

    def test_create_warehouse_audit_log(self, db: Session, admin_user: User) -> None:
        create_warehouse(db, WarehouseCreate(name="Audit WH"), admin_user.id)
        log = (
            db.query(AuditLog)
            .filter(AuditLog.action == "WAREHOUSE_CREATED")
            .first()
        )
        assert log is not None
        assert log.new_values["name"] == "Audit WH"

    def test_create_duplicate_name_fails(self, db: Session, admin_user: User) -> None:
        create_warehouse(db, WarehouseCreate(name="Dup"), admin_user.id)
        with pytest.raises(Exception):
            create_warehouse(db, WarehouseCreate(name="Dup"), admin_user.id)

    def test_update_warehouse(
        self, db: Session, admin_user: User, warehouse_main: Warehouse
    ) -> None:
        data = WarehouseUpdate(name="Renamed", address="New Addr")
        result = update_warehouse(db, warehouse_main.id, data, admin_user.id)
        assert result.name == "Renamed"
        assert result.address == "New Addr"

    def test_update_warehouse_deactivate(
        self, db: Session, admin_user: User, warehouse_main: Warehouse
    ) -> None:
        update_warehouse(
            db, warehouse_main.id, WarehouseUpdate(is_active=False), admin_user.id
        )
        # Inactive warehouses excluded from list
        active = list_warehouses(db)
        assert all(w.id != warehouse_main.id for w in active)

    def test_update_nonexistent_raises(self, db: Session, admin_user: User) -> None:
        with pytest.raises(ValueError, match="Warehouse not found"):
            update_warehouse(
                db, uuid.uuid4(), WarehouseUpdate(name="X"), admin_user.id
            )

    def test_list_warehouses_ordered(self, db: Session, admin_user: User) -> None:
        create_warehouse(db, WarehouseCreate(name="Zeta"), admin_user.id)
        create_warehouse(db, WarehouseCreate(name="Alpha"), admin_user.id)
        result = list_warehouses(db)
        names = [w.name for w in result]
        assert names == sorted(names)

    def test_warehouse_stock_empty(
        self, db: Session, warehouse_main: Warehouse
    ) -> None:
        stock = get_warehouse_stock(db, warehouse_main.id)
        assert stock == []

    def test_warehouse_stock_with_items(
        self,
        db: Session,
        warehouse_main: Warehouse,
        stock_at_main: list,
        product_a,
        product_b,
    ) -> None:
        stock = get_warehouse_stock(db, warehouse_main.id)
        assert len(stock) == 2
        skus = {s.product_sku for s in stock}
        assert skus == {"SKU-A", "SKU-B"}

    def test_warehouse_stock_nonexistent_raises(self, db: Session) -> None:
        with pytest.raises(ValueError, match="Warehouse not found"):
            get_warehouse_stock(db, uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════════════════
#  API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWarehouseAPI:
    def test_list_warehouses_ok(self, client, admin_token: str) -> None:
        r = client.get("/api/v1/warehouses", headers=auth(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_warehouse_admin(self, client, admin_token: str) -> None:
        r = client.post(
            "/api/v1/warehouses",
            json={"name": "New WH", "address": "Riyadh"},
            headers=auth(admin_token),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "New WH"
        assert body["is_active"] is True

    def test_create_warehouse_cashier_forbidden(
        self, client, cashier_token: str
    ) -> None:
        r = client.post(
            "/api/v1/warehouses",
            json={"name": "Nope"},
            headers=auth(cashier_token),
        )
        assert r.status_code == 403

    def test_update_warehouse_admin(
        self, client, admin_token: str, db: Session, warehouse_main: Warehouse
    ) -> None:
        r = client.patch(
            f"/api/v1/warehouses/{warehouse_main.id}",
            json={"name": "Updated Name"},
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

    def test_get_warehouse_stock(
        self,
        client,
        admin_token: str,
        db: Session,
        warehouse_main: Warehouse,
        stock_at_main: list,
    ) -> None:
        r = client.get(
            f"/api/v1/warehouses/{warehouse_main.id}/stock",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_get_stock_cashier_forbidden(
        self,
        client,
        cashier_token: str,
        db: Session,
        warehouse_main: Warehouse,
    ) -> None:
        r = client.get(
            f"/api/v1/warehouses/{warehouse_main.id}/stock",
            headers=auth(cashier_token),
        )
        assert r.status_code == 403

    def test_list_warehouses_returns_created(
        self, client, admin_token: str
    ) -> None:
        client.post(
            "/api/v1/warehouses",
            json={"name": "WH1"},
            headers=auth(admin_token),
        )
        r = client.get("/api/v1/warehouses", headers=auth(admin_token))
        assert r.status_code == 200
        names = [w["name"] for w in r.json()]
        assert "WH1" in names

    def test_unauthenticated_rejected(self, client) -> None:
        r = client.get("/api/v1/warehouses")
        assert r.status_code == 401
