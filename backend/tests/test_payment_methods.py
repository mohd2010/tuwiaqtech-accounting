"""Tests for payment method support in POS sales."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, TransactionSplit, User
from backend.app.models.inventory import Product
from backend.app.models.inventory import WarehouseStock
from backend.app.models.pos import Register, SalePayment, Shift, ShiftStatus
from backend.app.schemas.pos import PaymentEntry, PaymentMethodEnum, SaleItem
from backend.app.services.pos import (
    CASH_ACCOUNT_CODE,
    PAYMENT_METHOD_ACCOUNT_MAP,
    _compute_shift_sales,
    close_shift,
    open_shift,
    process_sale,
)
from backend.tests.conftest import auth

ZERO = Decimal("0")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_sale(
    db: Session,
    admin_user: User,
    product: Product,
    seed_accounts: dict[str, Account],
    payments: list[PaymentEntry] | None = None,
    quantity: int = 1,
) -> dict:
    items = [SaleItem(product_id=product.id, quantity=quantity)]
    return process_sale(
        db=db,
        items=items,
        user_id=admin_user.id,
        payments=payments,
    )


# ─── TestPaymentMethods ─────────────────────────────────────────────────────


class TestPaymentMethods:
    def test_cash_sale_debits_cash_account(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """Default (no payments) debits Cash account 1000."""
        result = _make_sale(db, admin_user, product_a, seed_accounts)
        cash_account = seed_accounts["1000"]
        journal_id = UUID(result["journal_entry_id"])

        debit_splits = (
            db.query(TransactionSplit)
            .filter(
                TransactionSplit.journal_entry_id == journal_id,
                TransactionSplit.account_id == cash_account.id,
                TransactionSplit.debit_amount > 0,
            )
            .all()
        )
        assert len(debit_splits) == 1
        assert debit_splits[0].debit_amount == Decimal(result["total_collected"])

    def test_card_sale_debits_bank_account(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """CARD payment debits Bank account 1200."""
        total = Decimal("100.0000")
        payments = [PaymentEntry(method=PaymentMethodEnum.CARD, amount=total)]
        result = _make_sale(db, admin_user, product_a, seed_accounts, payments=payments)
        bank_account = seed_accounts["1200"]
        journal_id = UUID(result["journal_entry_id"])

        debit_splits = (
            db.query(TransactionSplit)
            .filter(
                TransactionSplit.journal_entry_id == journal_id,
                TransactionSplit.account_id == bank_account.id,
                TransactionSplit.debit_amount > 0,
            )
            .all()
        )
        assert len(debit_splits) == 1
        assert debit_splits[0].debit_amount == Decimal(result["total_collected"])

    def test_split_payment_creates_two_debit_splits(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """Split payment creates two debit splits on different accounts."""
        total = Decimal("100.0000")
        cash_part = Decimal("60.0000")
        card_part = Decimal("40.0000")
        payments = [
            PaymentEntry(method=PaymentMethodEnum.CASH, amount=cash_part),
            PaymentEntry(method=PaymentMethodEnum.CARD, amount=card_part),
        ]
        result = _make_sale(db, admin_user, product_a, seed_accounts, payments=payments)
        journal_id = UUID(result["journal_entry_id"])

        cash_account = seed_accounts["1000"]
        bank_account = seed_accounts["1200"]

        cash_debits = (
            db.query(TransactionSplit)
            .filter(
                TransactionSplit.journal_entry_id == journal_id,
                TransactionSplit.account_id == cash_account.id,
                TransactionSplit.debit_amount > 0,
            )
            .all()
        )
        bank_debits = (
            db.query(TransactionSplit)
            .filter(
                TransactionSplit.journal_entry_id == journal_id,
                TransactionSplit.account_id == bank_account.id,
                TransactionSplit.debit_amount > 0,
            )
            .all()
        )
        assert len(cash_debits) == 1
        assert cash_debits[0].debit_amount == cash_part
        assert len(bank_debits) == 1
        assert bank_debits[0].debit_amount == card_part

    def test_payment_total_mismatch_raises(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """ValueError if sum of payments != grand_total."""
        payments = [PaymentEntry(method=PaymentMethodEnum.CASH, amount=Decimal("50.0000"))]
        with pytest.raises(ValueError, match="does not match"):
            _make_sale(db, admin_user, product_a, seed_accounts, payments=payments)

    def test_sale_payment_records_created(
        self, db: Session, admin_user: User, product_a: Product, seed_accounts: dict[str, Account]
    ) -> None:
        """SalePayment rows exist in DB after sale."""
        total = Decimal("100.0000")
        cash_part = Decimal("60.0000")
        card_part = Decimal("40.0000")
        payments = [
            PaymentEntry(method=PaymentMethodEnum.CASH, amount=cash_part),
            PaymentEntry(method=PaymentMethodEnum.CARD, amount=card_part),
        ]
        result = _make_sale(db, admin_user, product_a, seed_accounts, payments=payments)
        journal_id = UUID(result["journal_entry_id"])

        sale_payments = (
            db.query(SalePayment)
            .filter(SalePayment.journal_entry_id == journal_id)
            .order_by(SalePayment.amount.desc())
            .all()
        )
        assert len(sale_payments) == 2
        assert sale_payments[0].payment_method.value == "CASH"
        assert sale_payments[0].amount == cash_part
        assert sale_payments[1].payment_method.value == "CARD"
        assert sale_payments[1].amount == card_part


# ─── TestShiftCashTracking ───────────────────────────────────────────────────


class TestShiftCashTracking:
    def test_card_sale_excluded_from_shift_cash(
        self,
        db: Session,
        admin_user: User,
        product_a: Product,
        seed_accounts: dict[str, Account],
        register: Register,
    ) -> None:
        """Card-only sale does not count toward expected_cash."""
        shift_out = open_shift(db, admin_user.id, register.id, Decimal("100"))
        shift = db.query(Shift).filter(Shift.id == shift_out.id).first()
        assert shift is not None

        total = Decimal("100.0000")
        payments = [PaymentEntry(method=PaymentMethodEnum.CARD, amount=total)]
        _make_sale(db, admin_user, product_a, seed_accounts, payments=payments)

        cash_sales = _compute_shift_sales(db, admin_user.id, shift.opened_at)
        assert cash_sales == ZERO

    def test_split_payment_only_counts_cash_portion(
        self,
        db: Session,
        admin_user: User,
        product_a: Product,
        seed_accounts: dict[str, Account],
        register: Register,
    ) -> None:
        """Only the cash portion of a split payment counts toward shift cash."""
        shift_out = open_shift(db, admin_user.id, register.id, Decimal("100"))
        shift = db.query(Shift).filter(Shift.id == shift_out.id).first()
        assert shift is not None

        total = Decimal("100.0000")
        cash_part = Decimal("60.0000")
        card_part = Decimal("40.0000")
        payments = [
            PaymentEntry(method=PaymentMethodEnum.CASH, amount=cash_part),
            PaymentEntry(method=PaymentMethodEnum.CARD, amount=card_part),
        ]
        _make_sale(db, admin_user, product_a, seed_accounts, payments=payments)

        cash_sales = _compute_shift_sales(db, admin_user.id, shift.opened_at)
        assert cash_sales == cash_part


# ─── TestPaymentMethodAPI ────────────────────────────────────────────────────


class TestPaymentMethodAPI:
    def test_sale_with_card_payment_via_api(
        self,
        client,
        db: Session,
        admin_user: User,
        admin_token: str,
        product_a: Product,
        seed_accounts: dict[str, Account],
        register: Register,
        stock_at_main: list[WarehouseStock],
    ) -> None:
        """POST /pos/sale with card payment via API."""
        # Open shift first
        client.post(
            "/api/v1/pos/shifts/open",
            json={"register_id": str(register.id), "opening_cash": "100"},
            headers=auth(admin_token),
        )
        res = client.post(
            "/api/v1/pos/sale",
            json={
                "items": [{"product_id": str(product_a.id), "quantity": 1}],
                "payments": [{"method": "CARD", "amount": "100.0000"}],
            },
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["payments"]) == 1
        assert data["payments"][0]["method"] == "CARD"

    def test_sale_with_split_payment_via_api(
        self,
        client,
        db: Session,
        admin_user: User,
        admin_token: str,
        product_a: Product,
        seed_accounts: dict[str, Account],
        register: Register,
        stock_at_main: list[WarehouseStock],
    ) -> None:
        """POST /pos/sale with split payment via API."""
        client.post(
            "/api/v1/pos/shifts/open",
            json={"register_id": str(register.id), "opening_cash": "100"},
            headers=auth(admin_token),
        )
        res = client.post(
            "/api/v1/pos/sale",
            json={
                "items": [{"product_id": str(product_a.id), "quantity": 1}],
                "payments": [
                    {"method": "CASH", "amount": "60.0000"},
                    {"method": "CARD", "amount": "40.0000"},
                ],
            },
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["payments"]) == 2

    def test_invoice_includes_payment_details(
        self,
        client,
        db: Session,
        admin_user: User,
        admin_token: str,
        product_a: Product,
        seed_accounts: dict[str, Account],
        register: Register,
        stock_at_main: list[WarehouseStock],
    ) -> None:
        """Response includes payments array."""
        client.post(
            "/api/v1/pos/shifts/open",
            json={"register_id": str(register.id), "opening_cash": "100"},
            headers=auth(admin_token),
        )
        res = client.post(
            "/api/v1/pos/sale",
            json={
                "items": [{"product_id": str(product_a.id), "quantity": 1}],
            },
            headers=auth(admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert "payments" in data
        assert len(data["payments"]) == 1
        assert data["payments"][0]["method"] == "CASH"
