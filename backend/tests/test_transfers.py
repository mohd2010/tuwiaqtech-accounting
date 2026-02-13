"""Tests for the stock transfer lifecycle — service layer + API endpoints."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import AuditLog, User
from backend.app.models.inventory import (
    Product,
    Warehouse,
    WarehouseStock,
)
from backend.app.schemas.warehouse import TransferCreate, TransferItemCreate
from backend.app.services.warehouse import (
    cancel_transfer,
    create_transfer,
    list_transfers,
    receive_transfer,
    ship_transfer,
)
from backend.tests.conftest import auth


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_transfer_data(
    from_id: uuid.UUID,
    to_id: uuid.UUID,
    product_id: uuid.UUID,
    qty: int = 5,
    notes: str | None = None,
) -> TransferCreate:
    return TransferCreate(
        from_warehouse_id=from_id,
        to_warehouse_id=to_id,
        items=[TransferItemCreate(product_id=product_id, quantity=qty)],
        notes=notes,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Service-layer tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransferCreate:
    def test_create_deducts_source_stock(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        data = _make_transfer_data(warehouse_main.id, warehouse_branch.id, product_a.id, 10)
        result = create_transfer(db, data, admin_user.id)
        assert result.status == "PENDING"

        # Source warehouse_stock decreased
        ws = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == warehouse_main.id,
                WarehouseStock.product_id == product_a.id,
            )
            .first()
        )
        assert ws.quantity == 40  # 50 - 10

        # Global product.current_stock also decreased
        db.refresh(product_a)
        assert product_a.current_stock == 40

    def test_create_audit_logged(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a)
        log = db.query(AuditLog).filter(AuditLog.action == "TRANSFER_CREATED").first()
        assert log is not None

    def test_create_insufficient_stock_raises(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        data = _make_transfer_data(warehouse_main.id, warehouse_branch.id, product_a.id, 999)
        with pytest.raises(ValueError, match="Insufficient stock"):
            create_transfer(db, data, admin_user.id)

    def test_create_same_warehouse_raises(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        data = _make_transfer_data(warehouse_main.id, warehouse_main.id, product_a.id, 1)
        with pytest.raises(ValueError, match="different"):
            create_transfer(db, data, admin_user.id)

    def test_create_nonexistent_source_raises(
        self,
        db: Session,
        admin_user: User,
        warehouse_branch: Warehouse,
        product_a: Product,
    ) -> None:
        data = _make_transfer_data(uuid.uuid4(), warehouse_branch.id, product_a.id)
        with pytest.raises(ValueError, match="Source warehouse not found"):
            create_transfer(db, data, admin_user.id)

    def test_create_nonexistent_destination_raises(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        data = _make_transfer_data(warehouse_main.id, uuid.uuid4(), product_a.id)
        with pytest.raises(ValueError, match="Destination warehouse not found"):
            create_transfer(db, data, admin_user.id)

    def test_create_nonexistent_product_raises(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        stock_at_main: list,
    ) -> None:
        data = _make_transfer_data(warehouse_main.id, warehouse_branch.id, uuid.uuid4())
        with pytest.raises(ValueError, match="not found"):
            create_transfer(db, data, admin_user.id)

    def test_create_multi_item_transfer(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        product_b: Product,
        stock_at_main: list,
    ) -> None:
        data = TransferCreate(
            from_warehouse_id=warehouse_main.id,
            to_warehouse_id=warehouse_branch.id,
            items=[
                TransferItemCreate(product_id=product_a.id, quantity=3),
                TransferItemCreate(product_id=product_b.id, quantity=2),
            ],
        )
        result = create_transfer(db, data, admin_user.id)
        assert len(result.items) == 2


class TestTransferShip:
    def test_ship_pending_succeeds(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        t = _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a)
        result = ship_transfer(db, t.id, admin_user.id)
        assert result.status == "SHIPPED"

    def test_ship_already_shipped_raises(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        t = _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a)
        ship_transfer(db, t.id, admin_user.id)
        with pytest.raises(ValueError, match="Cannot ship"):
            ship_transfer(db, t.id, admin_user.id)

    def test_ship_nonexistent_raises(self, db: Session, admin_user: User) -> None:
        with pytest.raises(ValueError, match="Transfer not found"):
            ship_transfer(db, uuid.uuid4(), admin_user.id)


class TestTransferReceive:
    def test_receive_shipped_adds_destination_stock(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        t = _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a, qty=10)
        ship_transfer(db, t.id, admin_user.id)
        result = receive_transfer(db, t.id, admin_user.id)
        assert result.status == "RECEIVED"

        # Destination warehouse_stock was created/incremented
        ws_dest = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == warehouse_branch.id,
                WarehouseStock.product_id == product_a.id,
            )
            .first()
        )
        assert ws_dest is not None
        assert ws_dest.quantity == 10

        # Global product.current_stock restored (net zero effect for completed transfer)
        db.refresh(product_a)
        assert product_a.current_stock == 50  # back to original

    def test_receive_pending_directly(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        """Can receive a PENDING transfer without shipping first."""
        t = _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a, qty=5)
        result = receive_transfer(db, t.id, admin_user.id)
        assert result.status == "RECEIVED"

    def test_receive_cancelled_raises(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        t = _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a)
        cancel_transfer(db, t.id, admin_user.id)
        with pytest.raises(ValueError, match="Cannot receive"):
            receive_transfer(db, t.id, admin_user.id)

    def test_receive_already_received_raises(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        t = _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a)
        receive_transfer(db, t.id, admin_user.id)
        with pytest.raises(ValueError, match="Cannot receive"):
            receive_transfer(db, t.id, admin_user.id)


class TestTransferCancel:
    def test_cancel_pending_returns_stock(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        t = _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a, qty=10)
        result = cancel_transfer(db, t.id, admin_user.id)
        assert result.status == "CANCELLED"

        # Source warehouse_stock restored
        ws = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == warehouse_main.id,
                WarehouseStock.product_id == product_a.id,
            )
            .first()
        )
        assert ws.quantity == 50

        # Global product.current_stock also restored
        db.refresh(product_a)
        assert product_a.current_stock == 50

    def test_cancel_shipped_returns_stock(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        t = _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a, qty=10)
        ship_transfer(db, t.id, admin_user.id)
        cancel_transfer(db, t.id, admin_user.id)

        db.refresh(product_a)
        assert product_a.current_stock == 50

    def test_cancel_received_raises(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        t = _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a)
        receive_transfer(db, t.id, admin_user.id)
        with pytest.raises(ValueError, match="Cannot cancel"):
            cancel_transfer(db, t.id, admin_user.id)


class TestTransferList:
    def test_list_returns_recent_first(
        self,
        db: Session,
        admin_user: User,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a, qty=1)
        _make_and_create(db, admin_user, warehouse_main, warehouse_branch, product_a, qty=2)
        transfers = list_transfers(db)
        assert len(transfers) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
#  API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransferAPI:
    def test_create_transfer_api(
        self,
        client,
        admin_token: str,
        db: Session,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        r = client.post(
            "/api/v1/warehouses/transfers",
            json={
                "from_warehouse_id": str(warehouse_main.id),
                "to_warehouse_id": str(warehouse_branch.id),
                "items": [{"product_id": str(product_a.id), "quantity": 5}],
                "notes": "Test transfer",
            },
            headers=auth(admin_token),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "PENDING"
        assert body["notes"] == "Test transfer"
        assert len(body["items"]) == 1

    def test_ship_transfer_api(
        self,
        client,
        admin_token: str,
        db: Session,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        create_r = client.post(
            "/api/v1/warehouses/transfers",
            json={
                "from_warehouse_id": str(warehouse_main.id),
                "to_warehouse_id": str(warehouse_branch.id),
                "items": [{"product_id": str(product_a.id), "quantity": 3}],
            },
            headers=auth(admin_token),
        )
        tid = create_r.json()["id"]

        r = client.post(
            f"/api/v1/warehouses/transfers/{tid}/ship",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "SHIPPED"

    def test_receive_transfer_api(
        self,
        client,
        admin_token: str,
        db: Session,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        create_r = client.post(
            "/api/v1/warehouses/transfers",
            json={
                "from_warehouse_id": str(warehouse_main.id),
                "to_warehouse_id": str(warehouse_branch.id),
                "items": [{"product_id": str(product_a.id), "quantity": 5}],
            },
            headers=auth(admin_token),
        )
        tid = create_r.json()["id"]

        r = client.post(
            f"/api/v1/warehouses/transfers/{tid}/receive",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "RECEIVED"

    def test_cancel_transfer_api(
        self,
        client,
        admin_token: str,
        db: Session,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        create_r = client.post(
            "/api/v1/warehouses/transfers",
            json={
                "from_warehouse_id": str(warehouse_main.id),
                "to_warehouse_id": str(warehouse_branch.id),
                "items": [{"product_id": str(product_a.id), "quantity": 2}],
            },
            headers=auth(admin_token),
        )
        tid = create_r.json()["id"]

        r = client.post(
            f"/api/v1/warehouses/transfers/{tid}/cancel",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "CANCELLED"

    def test_list_transfers_api(
        self, client, admin_token: str
    ) -> None:
        r = client.get(
            "/api/v1/warehouses/transfers",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_cashier_cannot_create_transfer(
        self,
        client,
        cashier_token: str,
        db: Session,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        r = client.post(
            "/api/v1/warehouses/transfers",
            json={
                "from_warehouse_id": str(warehouse_main.id),
                "to_warehouse_id": str(warehouse_branch.id),
                "items": [{"product_id": str(product_a.id), "quantity": 1}],
            },
            headers=auth(cashier_token),
        )
        assert r.status_code == 403

    def test_accountant_can_create_transfer(
        self,
        client,
        accountant_token: str,
        db: Session,
        warehouse_main: Warehouse,
        warehouse_branch: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        r = client.post(
            "/api/v1/warehouses/transfers",
            json={
                "from_warehouse_id": str(warehouse_main.id),
                "to_warehouse_id": str(warehouse_branch.id),
                "items": [{"product_id": str(product_a.id), "quantity": 1}],
            },
            headers=auth(accountant_token),
        )
        assert r.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper
# ═══════════════════════════════════════════════════════════════════════════════


def _make_and_create(
    db: Session,
    user: User,
    from_wh: Warehouse,
    to_wh: Warehouse,
    product: Product,
    qty: int = 5,
):
    data = _make_transfer_data(from_wh.id, to_wh.id, product.id, qty)
    return create_transfer(db, data, user.id)
