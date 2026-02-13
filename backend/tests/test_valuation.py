"""Tests for the Inventory Valuation report."""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.inventory import (
    Category,
    Product,
    Warehouse,
    WarehouseStock,
)
from backend.app.services.reports import get_inventory_valuation
from backend.tests.conftest import auth


# ── Service-level tests ──────────────────────────────────────────────────────


class TestValuationService:
    """Service function tests for inventory valuation."""

    def test_valuation_returns_products(
        self, db: Session, product_a: Product, product_b: Product,
    ) -> None:
        data = get_inventory_valuation(db)
        skus = [item["sku"] for item in data["items"]]
        assert "SKU-A" in skus
        assert "SKU-B" in skus

    def test_valuation_totals(
        self, db: Session, product_a: Product, product_b: Product,
    ) -> None:
        data = get_inventory_valuation(db)
        item_sum = sum(Decimal(i["total_value"]) for i in data["items"])
        assert Decimal(str(data["total_value"])) == item_sum

    def test_valuation_cost_calculation(
        self, db: Session, product_a: Product, product_b: Product,
    ) -> None:
        data = get_inventory_valuation(db)
        for item in data["items"]:
            expected = Decimal(item["cost_price"]) * item["quantity"]
            assert Decimal(item["total_value"]) == expected

    def test_filter_by_warehouse(
        self, db: Session, stock_at_main: list[WarehouseStock],
        warehouse_main: Warehouse,
    ) -> None:
        data = get_inventory_valuation(db, warehouse_id=warehouse_main.id)
        assert data["warehouse_filter"] == warehouse_main.name
        assert len(data["items"]) == 2

    def test_filter_by_category(
        self, db: Session, product_a: Product, category: Category,
    ) -> None:
        # Create a second category with a different product
        cat2 = Category(name="Other Category")
        db.add(cat2)
        db.flush()
        p = Product(
            name="Other Product", sku="SKU-OTHER",
            category_id=cat2.id, unit_price=Decimal("50.0000"),
            cost_price=Decimal("30.0000"), current_stock=10,
        )
        db.add(p)
        db.flush()

        data = get_inventory_valuation(db, category_id=category.id)
        assert data["category_filter"] == category.name
        # Only products from the test category
        for item in data["items"]:
            assert item["category"] == category.name

    def test_empty_valuation(self, db: Session) -> None:
        # Use a non-existent category to ensure empty results
        import uuid
        fake_cat_id = uuid.uuid4()
        data = get_inventory_valuation(db, category_id=fake_cat_id)
        assert data["items"] == []
        assert data["total_quantity"] == 0
        assert data["total_value"] == "0"


# ── API-level tests ──────────────────────────────────────────────────────────


class TestValuationAPI:
    """API endpoint tests for inventory valuation."""

    def test_valuation_endpoint(
        self, client: TestClient, admin_token: str,
        product_a: Product, product_b: Product,
    ) -> None:
        resp = client.get("/api/v1/reports/valuation", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        skus = [item["sku"] for item in data["items"]]
        assert "SKU-A" in skus
        assert "SKU-B" in skus

    def test_cashier_forbidden(
        self, client: TestClient, cashier_token: str,
    ) -> None:
        resp = client.get("/api/v1/reports/valuation", headers=auth(cashier_token))
        assert resp.status_code == 403

    def test_accountant_allowed(
        self, client: TestClient, accountant_token: str,
        product_a: Product,
    ) -> None:
        resp = client.get("/api/v1/reports/valuation", headers=auth(accountant_token))
        assert resp.status_code == 200

    def test_excel_export(
        self, client: TestClient, admin_token: str,
        seed_accounts: dict[str, object], product_a: Product,
    ) -> None:
        resp = client.get(
            "/api/v1/reports/valuation/export/excel",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]

    def test_pdf_export(
        self, client: TestClient, admin_token: str,
        seed_accounts: dict[str, object], product_a: Product,
    ) -> None:
        resp = client.get(
            "/api/v1/reports/valuation/export/pdf",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert "pdf" in resp.headers["content-type"]

    def test_filter_by_warehouse_param(
        self, client: TestClient, admin_token: str,
        stock_at_main: list[WarehouseStock], warehouse_main: Warehouse,
    ) -> None:
        resp = client.get(
            f"/api/v1/reports/valuation?warehouse_id={warehouse_main.id}",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["warehouse_filter"] == warehouse_main.name
