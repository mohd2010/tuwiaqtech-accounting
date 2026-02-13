"""Shared test fixtures.

Each test runs inside a nested DB transaction that is rolled back after the
test completes, so tests never pollute each other or the real database.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal, engine, get_db
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.main import app
from backend.app.models.accounting import Account, AccountType, RoleEnum, User
from backend.app.models.customer import Customer
from backend.app.models.inventory import Category, Product, Warehouse, WarehouseStock
from backend.app.models.permission import Permission, Role, RolePermission
from backend.app.models.pos import Register


# ─── Permission seed data (mirrors migration) ───────────────────────────────

_ALL_PERMISSION_CODES: list[tuple[str, str, str]] = [
    ("account:read", "View chart of accounts", "accounting"),
    ("account:write", "Create/update/delete accounts", "accounting"),
    ("journal:read", "View journal entries", "accounting"),
    ("journal:write", "Create journal entries", "accounting"),
    ("pos:sale", "Process POS sales", "pos"),
    ("pos:shift", "Open/close shifts", "pos"),
    ("pos:shift_list", "View all shifts", "pos"),
    ("inventory:read", "View products and categories", "inventory"),
    ("inventory:write", "Create/update products and categories", "inventory"),
    ("inventory:adjust", "Create stock adjustments", "inventory"),
    ("warehouse:read", "View warehouses and stock", "warehouse"),
    ("warehouse:write", "Manage warehouses and transfers", "warehouse"),
    ("returns:process", "Process sales returns", "returns"),
    ("expense:read", "View expenses", "expenses"),
    ("expense:write", "Record expenses", "expenses"),
    ("sales:read", "View sales history", "sales"),
    ("quote:read", "View quotes", "sales"),
    ("quote:write", "Create/manage quotes", "sales"),
    ("supplier:read", "View suppliers", "suppliers"),
    ("supplier:write", "Manage suppliers", "suppliers"),
    ("purchase:read", "View purchase orders", "suppliers"),
    ("purchase:write", "Manage purchase orders and returns", "suppliers"),
    ("report:read", "View financial reports", "reports"),
    ("report:export", "Export reports to Excel/PDF", "reports"),
    ("banking:read", "View bank reconciliation", "banking"),
    ("banking:write", "Manage bank reconciliation", "banking"),
    ("invoice:read", "View credit invoices", "invoices"),
    ("invoice:write", "Create credit invoices and payments", "invoices"),
    ("fiscal:close", "Close fiscal year", "admin"),
    ("recurring:read", "View recurring entries", "admin"),
    ("recurring:write", "Manage recurring entries", "admin"),
    ("user:read", "View user list", "admin"),
    ("user:manage", "Create/update/delete users", "admin"),
    ("organization:read", "View organization settings", "admin"),
    ("organization:write", "Update organization settings", "admin"),
    ("einvoice:read", "View e-invoices", "zatca"),
    ("einvoice:write", "Submit e-invoices to ZATCA", "zatca"),
    ("audit:read", "View audit logs", "zatca"),
]

_ALL_CODES = [c for c, _, _ in _ALL_PERMISSION_CODES]

_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "ADMIN": _ALL_CODES,
    "ACCOUNTANT": [
        c for c in _ALL_CODES
        if c not in {
            "pos:sale", "pos:shift", "returns:process",
            "user:read", "user:manage",
            "organization:write", "fiscal:close",
            "einvoice:write",
        }
    ],
    "CASHIER": [
        "pos:sale", "pos:shift", "inventory:read", "sales:read",
        "returns:process", "account:read", "warehouse:read",
        "einvoice:read",
    ],
}


# ─── DB session that rolls back after every test ──────────────────────────────


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Yield a DB session wrapped in a SAVEPOINT; rolled back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    # Intercept commits inside service code → redirect to savepoint flush
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session: Session, trans: object) -> None:
        nonlocal nested
        if trans is nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired to the transactional test session."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ─── Roles & permissions ─────────────────────────────────────────────────────


@pytest.fixture()
def seed_roles(db: Session) -> dict[str, Role]:
    """Create Permission, Role, and RolePermission records.

    Returns a dict mapping role name to Role instance.
    """
    # Create permissions
    perm_map: dict[str, Permission] = {}
    for code, desc, cat in _ALL_PERMISSION_CODES:
        p = Permission(code=code, description=desc, category=cat)
        db.add(p)
        perm_map[code] = p
    db.flush()

    # Create roles + mappings
    roles: dict[str, Role] = {}
    for role_name, perm_codes in _ROLE_PERMISSIONS.items():
        role = Role(name=role_name, description=f"{role_name} role", is_system=True)
        db.add(role)
        db.flush()
        for code in perm_codes:
            db.add(RolePermission(role_id=role.id, permission_id=perm_map[code].id))
        roles[role_name] = role
    db.flush()
    return roles


# ─── Auth helpers ─────────────────────────────────────────────────────────────


@pytest.fixture()
def admin_user(db: Session, seed_roles: dict[str, Role]) -> User:
    user = User(
        username="test_admin",
        hashed_password=get_password_hash("pass"),
        role=RoleEnum.ADMIN,
        role_id=seed_roles["ADMIN"].id,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def accountant_user(db: Session, seed_roles: dict[str, Role]) -> User:
    user = User(
        username="test_accountant",
        hashed_password=get_password_hash("pass"),
        role=RoleEnum.ACCOUNTANT,
        role_id=seed_roles["ACCOUNTANT"].id,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def cashier_user(db: Session, seed_roles: dict[str, Role]) -> User:
    user = User(
        username="test_cashier",
        hashed_password=get_password_hash("pass"),
        role=RoleEnum.CASHIER,
        role_id=seed_roles["CASHIER"].id,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def admin_token(admin_user: User) -> str:
    return create_access_token(subject=str(admin_user.id))


@pytest.fixture()
def accountant_token(accountant_user: User) -> str:
    return create_access_token(subject=str(accountant_user.id))


@pytest.fixture()
def cashier_token(cashier_user: User) -> str:
    return create_access_token(subject=str(cashier_user.id))


def auth(token: str) -> dict[str, str]:
    """Return Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


# ─── Chart of Accounts (minimal set needed by POS / inventory services) ──────


@pytest.fixture()
def seed_accounts(db: Session) -> dict[str, Account]:
    """Return the chart of accounts required by services.

    Uses existing seeded rows when available, creates missing ones.
    """
    accounts: dict[str, Account] = {}
    for code, name, atype in [
        ("1000", "Cash", AccountType.ASSET),
        ("1100", "Inventory", AccountType.ASSET),
        ("2200", "VAT Payable", AccountType.LIABILITY),
        ("4000", "Sales", AccountType.REVENUE),
        ("4200", "Other Income", AccountType.REVENUE),
        ("5000", "COGS", AccountType.EXPENSE),
        ("1200", "Bank", AccountType.ASSET),
        ("4100", "Sales Discounts", AccountType.REVENUE),
        ("5200", "Inventory Shrinkage", AccountType.EXPENSE),
        ("5300", "Cash Shortage", AccountType.EXPENSE),
        ("1300", "Accounts Receivable", AccountType.ASSET),
        ("2100", "Supplier Payables", AccountType.LIABILITY),
        ("3000", "Retained Earnings", AccountType.EQUITY),
    ]:
        existing = db.query(Account).filter(Account.code == code).first()
        if existing:
            accounts[code] = existing
        else:
            acc = Account(code=code, name=name, account_type=atype, is_system=True)
            db.add(acc)
            accounts[code] = acc
    db.flush()
    return accounts


# ─── Inventory fixtures ───────────────────────────────────────────────────────


@pytest.fixture()
def category(db: Session) -> Category:
    cat = Category(name="Test Category")
    db.add(cat)
    db.flush()
    return cat


@pytest.fixture()
def product_a(db: Session, category: Category) -> Product:
    p = Product(
        name="Product A",
        sku="SKU-A",
        category_id=category.id,
        unit_price=Decimal("100.0000"),
        cost_price=Decimal("60.0000"),
        current_stock=50,
        reorder_level=5,
    )
    db.add(p)
    db.flush()
    return p


@pytest.fixture()
def product_b(db: Session, category: Category) -> Product:
    p = Product(
        name="Product B",
        sku="SKU-B",
        category_id=category.id,
        unit_price=Decimal("200.0000"),
        cost_price=Decimal("120.0000"),
        current_stock=30,
        reorder_level=3,
    )
    db.add(p)
    db.flush()
    return p


# ─── Warehouse fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def warehouse_main(db: Session) -> Warehouse:
    wh = Warehouse(name="Test Main Store")
    db.add(wh)
    db.flush()
    return wh


@pytest.fixture()
def warehouse_branch(db: Session) -> Warehouse:
    wh = Warehouse(name="Test Branch A")
    db.add(wh)
    db.flush()
    return wh


@pytest.fixture()
def stock_at_main(
    db: Session,
    warehouse_main: Warehouse,
    product_a: Product,
    product_b: Product,
) -> list[WarehouseStock]:
    """Pre-populate Main Store with stock matching the product current_stock."""
    ws_a = WarehouseStock(
        warehouse_id=warehouse_main.id,
        product_id=product_a.id,
        quantity=50,
    )
    ws_b = WarehouseStock(
        warehouse_id=warehouse_main.id,
        product_id=product_b.id,
        quantity=30,
    )
    db.add_all([ws_a, ws_b])
    db.flush()
    return [ws_a, ws_b]


# ─── Register fixture ────────────────────────────────────────────────────────


@pytest.fixture()
def register(db: Session, warehouse_main: Warehouse) -> Register:
    reg = Register(
        name="Test Counter 1",
        location="Test Main Store",
        warehouse_id=warehouse_main.id,
    )
    db.add(reg)
    db.flush()
    return reg


# ─── Customer fixture ───────────────────────────────────────────────────────


@pytest.fixture()
def customer(db: Session) -> Customer:
    c = Customer(
        name="Test B2B Customer",
        email="b2b@test.com",
        phone="0501234567",
        payment_terms_days=30,
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture()
def customer_with_limit(db: Session) -> Customer:
    c = Customer(
        name="Limited Customer",
        email="limited@test.com",
        phone="0509876543",
        payment_terms_days=30,
        credit_limit=Decimal("500.0000"),
    )
    db.add(c)
    db.flush()
    return c
