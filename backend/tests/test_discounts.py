"""Tests for POS discount support."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, TransactionSplit, User
from backend.app.models.inventory import Product, Warehouse, WarehouseStock
from backend.app.models.pos import Register, SaleDiscount, Shift, ShiftStatus
from backend.app.schemas.pos import PaymentEntry, PaymentMethodEnum, SaleItem
from backend.app.services.pos import (
    DISCOUNT_ACCOUNT_CODE,
    process_sale,
    open_shift,
)
from backend.tests.conftest import auth

ZERO = Decimal("0")
Q = Decimal("0.0001")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_sale(
    db: Session,
    admin_user: User,
    product: Product,
    seed_accounts: dict[str, Account],
    payments: list[PaymentEntry] | None = None,
    quantity: int = 1,
    discount_type: str | None = None,
    discount_value: Decimal | None = None,
) -> dict:
    items = [SaleItem(product_id=product.id, quantity=quantity)]
    return process_sale(
        db=db,
        items=items,
        user_id=admin_user.id,
        payments=payments,
        discount_type=discount_type,
        discount_value=discount_value,
    )


def _sum_debits(db: Session, journal_id: UUID) -> Decimal:
    splits = db.query(TransactionSplit).filter(
        TransactionSplit.journal_entry_id == journal_id
    ).all()
    return sum(Decimal(str(s.debit_amount)) for s in splits)


def _sum_credits(db: Session, journal_id: UUID) -> Decimal:
    splits = db.query(TransactionSplit).filter(
        TransactionSplit.journal_entry_id == journal_id
    ).all()
    return sum(Decimal(str(s.credit_amount)) for s in splits)


# ─── TestPercentageDiscount ──────────────────────────────────────────────────


class TestPercentageDiscount:
    def test_percentage_discount_reduces_total(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """10% off 100 SAR -> customer pays 90 SAR."""
        result = _make_sale(
            db, admin_user, product_a, seed_accounts,
            discount_type="PERCENTAGE", discount_value=Decimal("10"),
        )
        assert Decimal(result["total_collected"]) == Decimal("90.0000")
        assert Decimal(result["discount_amount"]) == Decimal("10.0000")
        assert result["original_total"] == "100.0000"

    def test_percentage_discount_journal_balanced(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """sum(debits) == sum(credits) for discounted sale."""
        result = _make_sale(
            db, admin_user, product_a, seed_accounts,
            discount_type="PERCENTAGE", discount_value=Decimal("10"),
        )
        journal_id = UUID(result["journal_entry_id"])
        assert _sum_debits(db, journal_id) == _sum_credits(db, journal_id)

    def test_percentage_discount_debits_discount_account(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """Sales Discounts (4100) receives a debit when discount applied."""
        result = _make_sale(
            db, admin_user, product_a, seed_accounts,
            discount_type="PERCENTAGE", discount_value=Decimal("10"),
        )
        journal_id = UUID(result["journal_entry_id"])
        discount_account = seed_accounts["4100"]

        debit_splits = (
            db.query(TransactionSplit)
            .filter(
                TransactionSplit.journal_entry_id == journal_id,
                TransactionSplit.account_id == discount_account.id,
                TransactionSplit.debit_amount > 0,
            )
            .all()
        )
        assert len(debit_splits) == 1
        assert debit_splits[0].debit_amount > ZERO


# ─── TestFixedDiscount ───────────────────────────────────────────────────────


class TestFixedDiscount:
    def test_fixed_discount_reduces_total(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """15 SAR off 100 SAR -> customer pays 85 SAR."""
        result = _make_sale(
            db, admin_user, product_a, seed_accounts,
            discount_type="FIXED_AMOUNT", discount_value=Decimal("15"),
        )
        assert Decimal(result["total_collected"]) == Decimal("85.0000")
        assert Decimal(result["discount_amount"]) == Decimal("15.0000")

    def test_fixed_discount_journal_balanced(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """sum(debits) == sum(credits) for fixed discount sale."""
        result = _make_sale(
            db, admin_user, product_a, seed_accounts,
            discount_type="FIXED_AMOUNT", discount_value=Decimal("15"),
        )
        journal_id = UUID(result["journal_entry_id"])
        assert _sum_debits(db, journal_id) == _sum_credits(db, journal_id)


# ─── TestDiscountValidation ─────────────────────────────────────────────────


class TestDiscountValidation:
    def test_discount_exceeding_total_raises(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """Discount >= sale total raises ValueError."""
        with pytest.raises(ValueError, match="Discount cannot equal or exceed"):
            _make_sale(
                db, admin_user, product_a, seed_accounts,
                discount_type="FIXED_AMOUNT", discount_value=Decimal("150"),
            )

    def test_discount_100_percent_raises(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """100% discount is rejected by the schema validator, but if called
        directly it should fail because discount equals total."""
        with pytest.raises(ValueError, match="Discount cannot equal or exceed"):
            _make_sale(
                db, admin_user, product_a, seed_accounts,
                discount_type="PERCENTAGE", discount_value=Decimal("100"),
            )

    def test_discount_value_zero_raises(
        self,
    ) -> None:
        """Schema rejects discount_value <= 0."""
        from backend.app.schemas.pos import SaleRequest, SaleItem as SchemaItem, DiscountTypeEnum
        with pytest.raises(Exception):
            SaleRequest(
                items=[SchemaItem(product_id="00000000-0000-0000-0000-000000000001", quantity=1)],
                discount_type=DiscountTypeEnum.PERCENTAGE,
                discount_value=Decimal("0"),
            )


# ─── TestDiscountWithPayments ────────────────────────────────────────────────


class TestDiscountWithPayments:
    def test_discount_with_card_payment(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """CARD payment for discounted total works correctly."""
        discounted_total = Decimal("90.0000")
        payments = [PaymentEntry(method=PaymentMethodEnum.CARD, amount=discounted_total)]
        result = _make_sale(
            db, admin_user, product_a, seed_accounts,
            payments=payments,
            discount_type="PERCENTAGE", discount_value=Decimal("10"),
        )
        assert Decimal(result["total_collected"]) == discounted_total
        journal_id = UUID(result["journal_entry_id"])
        assert _sum_debits(db, journal_id) == _sum_credits(db, journal_id)

    def test_discount_with_split_payment(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """Split payment matching discounted total works correctly."""
        cash_part = Decimal("50.0000")
        card_part = Decimal("40.0000")
        payments = [
            PaymentEntry(method=PaymentMethodEnum.CASH, amount=cash_part),
            PaymentEntry(method=PaymentMethodEnum.CARD, amount=card_part),
        ]
        result = _make_sale(
            db, admin_user, product_a, seed_accounts,
            payments=payments,
            discount_type="PERCENTAGE", discount_value=Decimal("10"),
        )
        assert Decimal(result["total_collected"]) == Decimal("90.0000")
        journal_id = UUID(result["journal_entry_id"])
        assert _sum_debits(db, journal_id) == _sum_credits(db, journal_id)


# ─── TestDiscountShiftTracking ───────────────────────────────────────────────


class TestDiscountShiftTracking:
    def test_discount_sale_shift_cash(
        self,
        db: Session,
        admin_user: User,
        product_a: Product,
        seed_accounts: dict[str, Account],
        register: Register,
        stock_at_main: list[WarehouseStock],
    ) -> None:
        """Cash sale with discount: shift tracks discounted cash amount."""
        from backend.app.services.pos import _compute_shift_sales

        shift = open_shift(db, admin_user.id, register.id, Decimal("0"))

        result = process_sale(
            db=db,
            items=[SaleItem(product_id=product_a.id, quantity=1)],
            user_id=admin_user.id,
            warehouse_id=register.warehouse_id,
            discount_type="PERCENTAGE",
            discount_value=Decimal("10"),
        )

        shift_obj = db.query(Shift).filter(Shift.id == shift.id).first()
        assert shift_obj is not None
        total_sales = _compute_shift_sales(db, admin_user.id, shift_obj.opened_at)
        # Cash debited = discounted total = 90
        assert total_sales == Decimal("90.0000")


# ─── TestDiscountSaleRecord ──────────────────────────────────────────────────


class TestDiscountSaleRecord:
    def test_sale_discount_record_created(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """SaleDiscount row exists in DB after discounted sale."""
        result = _make_sale(
            db, admin_user, product_a, seed_accounts,
            discount_type="FIXED_AMOUNT", discount_value=Decimal("20"),
        )
        journal_id = UUID(result["journal_entry_id"])
        record = db.query(SaleDiscount).filter(
            SaleDiscount.journal_entry_id == journal_id
        ).first()
        assert record is not None
        assert record.discount_amount == Decimal("20.0000")
        assert record.discount_value == Decimal("20.0000")
        assert record.discount_type.value == "FIXED_AMOUNT"


# ─── TestDiscountAPI ─────────────────────────────────────────────────────────


class TestDiscountAPI:
    def test_sale_with_percentage_discount_via_api(
        self,
        client: object,
        db: Session,
        admin_user: User,
        admin_token: str,
        product_a: Product,
        seed_accounts: dict[str, Account],
        register: Register,
        stock_at_main: list[WarehouseStock],
    ) -> None:
        """POST /pos/sale with discount returns correct totals."""
        # Open a shift first
        client.post(  # type: ignore[union-attr]
            "/api/v1/pos/shifts/open",
            json={"register_id": str(register.id), "opening_cash": "0"},
            headers=auth(admin_token),
        )
        resp = client.post(  # type: ignore[union-attr]
            "/api/v1/pos/sale",
            json={
                "items": [{"product_id": str(product_a.id), "quantity": 1}],
                "discount_type": "PERCENTAGE",
                "discount_value": "10",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 200  # type: ignore[union-attr]
        data = resp.json()  # type: ignore[union-attr]
        assert Decimal(data["total_collected"]) == Decimal("90.0000")
        assert Decimal(data["discount_amount"]) == Decimal("10.0000")

    def test_invoice_includes_discount(
        self,
        client: object,
        db: Session,
        admin_user: User,
        admin_token: str,
        product_a: Product,
        seed_accounts: dict[str, Account],
        register: Register,
        stock_at_main: list[WarehouseStock],
    ) -> None:
        """Response includes discount_amount and original_total."""
        client.post(  # type: ignore[union-attr]
            "/api/v1/pos/shifts/open",
            json={"register_id": str(register.id), "opening_cash": "0"},
            headers=auth(admin_token),
        )
        resp = client.post(  # type: ignore[union-attr]
            "/api/v1/pos/sale",
            json={
                "items": [{"product_id": str(product_a.id), "quantity": 1}],
                "discount_type": "FIXED_AMOUNT",
                "discount_value": "25",
            },
            headers=auth(admin_token),
        )
        assert resp.status_code == 200  # type: ignore[union-attr]
        data = resp.json()  # type: ignore[union-attr]
        assert data["discount_amount"] == "25.0000"
        assert data["original_total"] == "100.0000"
        assert Decimal(data["total_collected"]) == Decimal("75.0000")
