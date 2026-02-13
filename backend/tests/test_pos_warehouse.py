"""Tests for warehouse-aware POS stock deduction."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, User
from backend.app.models.inventory import Product, Warehouse, WarehouseStock
from backend.app.models.pos import Register, Shift, ShiftStatus
from backend.app.schemas.pos import SaleItem
from backend.app.services.pos import process_sale
from backend.tests.conftest import auth


class TestPOSWarehouseDeduction:
    """process_sale() should deduct from WarehouseStock when warehouse_id is given."""

    def test_sale_deducts_warehouse_stock(
        self,
        db: Session,
        admin_user: User,
        seed_accounts: dict[str, Account],
        warehouse_main: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        items = [SaleItem(product_id=product_a.id, quantity=3)]
        process_sale(
            db,
            items=items,
            user_id=admin_user.id,
            warehouse_id=warehouse_main.id,
        )

        # Global stock decreased
        db.refresh(product_a)
        assert product_a.current_stock == 47  # 50 - 3

        # Warehouse stock also decreased
        ws = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == warehouse_main.id,
                WarehouseStock.product_id == product_a.id,
            )
            .first()
        )
        assert ws.quantity == 47

    def test_sale_without_warehouse_only_deducts_global(
        self,
        db: Session,
        admin_user: User,
        seed_accounts: dict[str, Account],
        warehouse_main: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        items = [SaleItem(product_id=product_a.id, quantity=2)]
        process_sale(
            db,
            items=items,
            user_id=admin_user.id,
            warehouse_id=None,
        )

        db.refresh(product_a)
        assert product_a.current_stock == 48

        # Warehouse stock unchanged
        ws = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == warehouse_main.id,
                WarehouseStock.product_id == product_a.id,
            )
            .first()
        )
        assert ws.quantity == 50

    def test_sale_insufficient_warehouse_stock_raises(
        self,
        db: Session,
        admin_user: User,
        seed_accounts: dict[str, Account],
        warehouse_main: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        # product_a has 50 global stock but only 50 at warehouse
        items = [SaleItem(product_id=product_a.id, quantity=999)]
        with pytest.raises(ValueError, match="Insufficient stock"):
            process_sale(
                db,
                items=items,
                user_id=admin_user.id,
                warehouse_id=warehouse_main.id,
            )

    def test_sale_multi_item_warehouse_deduction(
        self,
        db: Session,
        admin_user: User,
        seed_accounts: dict[str, Account],
        warehouse_main: Warehouse,
        product_a: Product,
        product_b: Product,
        stock_at_main: list,
    ) -> None:
        items = [
            SaleItem(product_id=product_a.id, quantity=5),
            SaleItem(product_id=product_b.id, quantity=3),
        ]
        result = process_sale(
            db,
            items=items,
            user_id=admin_user.id,
            warehouse_id=warehouse_main.id,
        )
        assert "invoice_number" in result

        db.refresh(product_a)
        db.refresh(product_b)
        assert product_a.current_stock == 45
        assert product_b.current_stock == 27

        ws_a = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == warehouse_main.id,
                WarehouseStock.product_id == product_a.id,
            )
            .first()
        )
        ws_b = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == warehouse_main.id,
                WarehouseStock.product_id == product_b.id,
            )
            .first()
        )
        assert ws_a.quantity == 45
        assert ws_b.quantity == 27


class TestPOSEndpointWarehouse:
    """The /pos/sale endpoint should resolve warehouse_id from the shift's register."""

    def test_sale_endpoint_deducts_from_register_warehouse(
        self,
        client,
        db: Session,
        admin_user: User,
        admin_token: str,
        seed_accounts: dict[str, Account],
        register: Register,
        warehouse_main: Warehouse,
        product_a: Product,
        stock_at_main: list,
    ) -> None:
        # Open a shift on the warehouse-linked register
        shift = Shift(
            register_id=register.id,
            user_id=admin_user.id,
            status=ShiftStatus.OPEN,
            opening_cash=Decimal("0"),
        )
        db.add(shift)
        db.flush()

        r = client.post(
            "/api/v1/pos/sale",
            json={
                "items": [{"product_id": str(product_a.id), "quantity": 4}],
            },
            headers=auth(admin_token),
        )
        assert r.status_code == 200

        # Verify warehouse stock was deducted (register → warehouse_main)
        ws = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == warehouse_main.id,
                WarehouseStock.product_id == product_a.id,
            )
            .first()
        )
        assert ws.quantity == 46  # 50 - 4

        db.refresh(product_a)
        assert product_a.current_stock == 46
