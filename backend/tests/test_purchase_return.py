"""Tests for Purchase Return (Debit Note) service and API."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, TransactionSplit
from backend.app.models.inventory import Product
from backend.app.models.supplier import (
    POStatus,
    PRStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReturn,
    Supplier,
)
from backend.app.services.purchase_return import lookup_po, process_purchase_return
from backend.tests.conftest import auth


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def supplier(db: Session) -> Supplier:
    s = Supplier(name="Test Supplier Co")
    db.add(s)
    db.flush()
    return s


@pytest.fixture()
def received_po(
    db: Session,
    supplier: Supplier,
    product_a: Product,
    product_b: Product,
    admin_user,
) -> PurchaseOrder:
    """Create and 'receive' a PO with product_a (10 units @ 60) and product_b (5 units @ 120)."""
    po = PurchaseOrder(
        supplier_id=supplier.id,
        status=POStatus.RECEIVED,
        total_amount=Decimal("1200.0000"),  # 10*60 + 5*120
        created_by=admin_user.id,
    )
    db.add(po)
    db.flush()

    db.add(PurchaseOrderItem(
        po_id=po.id,
        product_id=product_a.id,
        quantity=10,
        unit_cost=Decimal("60.0000"),
    ))
    db.add(PurchaseOrderItem(
        po_id=po.id,
        product_id=product_b.id,
        quantity=5,
        unit_cost=Decimal("120.0000"),
    ))
    db.flush()
    return po


@pytest.fixture()
def pending_po(
    db: Session,
    supplier: Supplier,
    product_a: Product,
    admin_user,
) -> PurchaseOrder:
    """A PO still in PENDING status."""
    po = PurchaseOrder(
        supplier_id=supplier.id,
        status=POStatus.PENDING,
        total_amount=Decimal("600.0000"),
        created_by=admin_user.id,
    )
    db.add(po)
    db.flush()
    db.add(PurchaseOrderItem(
        po_id=po.id,
        product_id=product_a.id,
        quantity=10,
        unit_cost=Decimal("60.0000"),
    ))
    db.flush()
    return po


# ─── Service Tests ───────────────────────────────────────────────────────────


class TestLookupPO:
    def test_lookup_received_po(
        self, db: Session, received_po: PurchaseOrder, seed_accounts,
    ):
        result = lookup_po(db, received_po.id)
        assert result["po_id"] == str(received_po.id)
        assert result["supplier_name"] == "Test Supplier Co"
        assert len(result["items"]) == 2
        # All quantities should be returnable
        for item in result["items"]:
            assert item["returnable_quantity"] == item["quantity_ordered"]
            assert item["quantity_returned"] == 0

    def test_lookup_pending_po_fails(
        self, db: Session, pending_po: PurchaseOrder, seed_accounts,
    ):
        with pytest.raises(ValueError, match="Cannot return items from PO with status PENDING"):
            lookup_po(db, pending_po.id)

    def test_lookup_nonexistent_po(self, db: Session, seed_accounts):
        with pytest.raises(ValueError, match="Purchase order not found"):
            lookup_po(db, uuid4())


class TestProcessPurchaseReturn:
    def test_process_return_basic(
        self,
        db: Session,
        received_po: PurchaseOrder,
        product_a: Product,
        admin_user,
        seed_accounts,
    ):
        initial_stock = product_a.current_stock
        result = process_purchase_return(
            db,
            po_id=received_po.id,
            items=[{
                "product_id": str(product_a.id),
                "quantity": 3,
                "condition": "RESALABLE",
            }],
            reason="Wrong items shipped",
            user_id=admin_user.id,
        )
        assert result["return_number"].startswith("PR-")
        assert result["supplier_name"] == "Test Supplier Co"
        assert result["total_amount"] == "180.0000"  # 3 * 60
        assert len(result["items"]) == 1
        assert result["items"][0]["product_name"] == "Product A"

    def test_return_journal_balanced(
        self,
        db: Session,
        received_po: PurchaseOrder,
        product_a: Product,
        admin_user,
        seed_accounts,
    ):
        result = process_purchase_return(
            db,
            po_id=received_po.id,
            items=[{
                "product_id": str(product_a.id),
                "quantity": 2,
                "condition": "RESALABLE",
            }],
            reason="Defective",
            user_id=admin_user.id,
        )
        # Verify journal entry is balanced
        from backend.app.models.accounting import JournalEntry
        je = db.query(JournalEntry).filter(
            JournalEntry.reference == result["return_number"]
        ).first()
        assert je is not None
        splits = db.query(TransactionSplit).filter(
            TransactionSplit.journal_entry_id == je.id
        ).all()
        total_debits = sum(Decimal(str(s.debit_amount)) for s in splits)
        total_credits = sum(Decimal(str(s.credit_amount)) for s in splits)
        assert total_debits == total_credits

    def test_return_stock_decreased(
        self,
        db: Session,
        received_po: PurchaseOrder,
        product_a: Product,
        admin_user,
        seed_accounts,
    ):
        initial_stock = product_a.current_stock
        process_purchase_return(
            db,
            po_id=received_po.id,
            items=[{
                "product_id": str(product_a.id),
                "quantity": 4,
                "condition": "RESALABLE",
            }],
            reason="Returns",
            user_id=admin_user.id,
        )
        assert product_a.current_stock == initial_stock - 4

    def test_return_damaged_uses_shrinkage(
        self,
        db: Session,
        received_po: PurchaseOrder,
        product_a: Product,
        admin_user,
        seed_accounts,
    ):
        result = process_purchase_return(
            db,
            po_id=received_po.id,
            items=[{
                "product_id": str(product_a.id),
                "quantity": 2,
                "condition": "DAMAGED",
            }],
            reason="Damaged on arrival",
            user_id=admin_user.id,
        )
        # Verify shrinkage account (5200) was credited
        from backend.app.models.accounting import JournalEntry
        je = db.query(JournalEntry).filter(
            JournalEntry.reference == result["return_number"]
        ).first()
        shrinkage_account = db.query(Account).filter(Account.code == "5200").first()
        shrinkage_splits = [
            s for s in db.query(TransactionSplit).filter(
                TransactionSplit.journal_entry_id == je.id,
                TransactionSplit.account_id == shrinkage_account.id,
            ).all()
        ]
        assert len(shrinkage_splits) == 1
        assert shrinkage_splits[0].credit_amount == Decimal("120.0000")  # 2 * 60

    def test_return_damaged_stock_also_decreased(
        self,
        db: Session,
        received_po: PurchaseOrder,
        product_a: Product,
        admin_user,
        seed_accounts,
    ):
        initial_stock = product_a.current_stock
        process_purchase_return(
            db,
            po_id=received_po.id,
            items=[{
                "product_id": str(product_a.id),
                "quantity": 2,
                "condition": "DAMAGED",
            }],
            reason="Damaged goods",
            user_id=admin_user.id,
        )
        assert product_a.current_stock == initial_stock - 2

    def test_partial_return(
        self,
        db: Session,
        received_po: PurchaseOrder,
        product_a: Product,
        admin_user,
        seed_accounts,
    ):
        # Return 3 of 10
        process_purchase_return(
            db,
            po_id=received_po.id,
            items=[{
                "product_id": str(product_a.id),
                "quantity": 3,
                "condition": "RESALABLE",
            }],
            reason="Partial return",
            user_id=admin_user.id,
        )
        # Check remaining returnable
        result = lookup_po(db, received_po.id)
        product_a_item = next(
            i for i in result["items"] if i["product_id"] == str(product_a.id)
        )
        assert product_a_item["returnable_quantity"] == 7  # 10 - 3

    def test_cannot_exceed_returnable(
        self,
        db: Session,
        received_po: PurchaseOrder,
        product_a: Product,
        admin_user,
        seed_accounts,
    ):
        with pytest.raises(ValueError, match="only 10 returnable"):
            process_purchase_return(
                db,
                po_id=received_po.id,
                items=[{
                    "product_id": str(product_a.id),
                    "quantity": 11,
                    "condition": "RESALABLE",
                }],
                reason="Too many",
                user_id=admin_user.id,
            )


# ─── API Tests ───────────────────────────────────────────────────────────────


class TestPurchaseReturnAPI:
    def test_lookup_endpoint(
        self, client, received_po, admin_token, seed_accounts,
    ):
        resp = client.get(
            f"/api/v1/purchase-returns/po/{received_po.id}",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["po_id"] == str(received_po.id)
        assert len(data["items"]) == 2

    def test_process_endpoint(
        self, client, received_po, product_a, admin_token, seed_accounts,
    ):
        resp = client.post(
            "/api/v1/purchase-returns/process",
            headers=auth(admin_token),
            json={
                "po_id": str(received_po.id),
                "items": [{
                    "product_id": str(product_a.id),
                    "quantity": 2,
                    "condition": "RESALABLE",
                }],
                "reason": "Defective batch",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["return_number"].startswith("PR-")
        assert data["total_amount"] == "120.0000"

    def test_list_returns(
        self, client, db, received_po, product_a, admin_user, admin_token, seed_accounts,
    ):
        # Create a return first
        process_purchase_return(
            db,
            po_id=received_po.id,
            items=[{
                "product_id": str(product_a.id),
                "quantity": 1,
                "condition": "RESALABLE",
            }],
            reason="Test",
            user_id=admin_user.id,
        )
        resp = client.get(
            "/api/v1/purchase-returns/",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["return_number"].startswith("PR-")

    def test_cashier_forbidden(
        self, client, received_po, cashier_token, seed_accounts,
    ):
        resp = client.get(
            f"/api/v1/purchase-returns/po/{received_po.id}",
            headers=auth(cashier_token),
        )
        assert resp.status_code == 403

    def test_accountant_allowed(
        self, client, received_po, accountant_token, seed_accounts,
    ):
        resp = client.get(
            f"/api/v1/purchase-returns/po/{received_po.id}",
            headers=auth(accountant_token),
        )
        assert resp.status_code == 200

    def test_invalid_po_returns_404(
        self, client, admin_token, seed_accounts,
    ):
        resp = client.get(
            f"/api/v1/purchase-returns/po/{uuid4()}",
            headers=auth(admin_token),
        )
        assert resp.status_code == 404
