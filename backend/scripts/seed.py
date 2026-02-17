"""Seed the database with an admin user and a standard chart of accounts.

Usage:
    python -m backend.scripts.seed
"""

from __future__ import annotations

from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models.accounting import Account, AccountType, RoleEnum, User
from backend.app.models.inventory import Warehouse
from backend.app.models.permission import Permission, Role, RolePermission
from backend.app.models.pos import Register

ACCOUNTS: list[tuple[str, str, AccountType]] = [
    # Assets
    ("1000", "Cash", AccountType.ASSET),
    ("1100", "Inventory", AccountType.ASSET),
    ("1200", "Bank", AccountType.ASSET),
    # Liabilities
    ("2000", "Accounts Payable", AccountType.LIABILITY),
    ("2100", "Supplier Payables", AccountType.LIABILITY),
    ("2200", "VAT Payable", AccountType.LIABILITY),
    # Equity
    ("3000", "Owner's Equity", AccountType.EQUITY),
    # Revenue
    ("4000", "Sales", AccountType.REVENUE),
    ("4200", "Other Income", AccountType.REVENUE),
    # Expenses
    ("5000", "Cost of Goods Sold", AccountType.EXPENSE),
    ("5100", "Rent", AccountType.EXPENSE),
    ("5110", "Utilities", AccountType.EXPENSE),
    ("5120", "Salaries & Wages", AccountType.EXPENSE),
    ("5130", "Marketing & Ads", AccountType.EXPENSE),
    ("5140", "Office Supplies", AccountType.EXPENSE),
    ("5200", "Inventory Shrinkage", AccountType.EXPENSE),
    ("5300", "Cash Shortage", AccountType.EXPENSE),
]

ALL_PERMISSION_CODES: list[tuple[str, str, str]] = [
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

ALL_CODES = [c for c, _, _ in ALL_PERMISSION_CODES]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "ADMIN": ALL_CODES,
    "ACCOUNTANT": [
        c for c in ALL_CODES
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


def seed() -> None:
    db = SessionLocal()
    try:
        # ── Permissions ────────────────────────────────────────────────
        perm_map: dict[str, Permission] = {}
        for code, desc, cat in ALL_PERMISSION_CODES:
            existing = db.query(Permission).filter_by(code=code).first()
            if existing:
                perm_map[code] = existing
            else:
                p = Permission(code=code, description=desc, category=cat)
                db.add(p)
                perm_map[code] = p
                print(f"Created permission: {code}")
        db.flush()

        # ── Roles ──────────────────────────────────────────────────────
        roles: dict[str, Role] = {}
        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            existing_role = db.query(Role).filter_by(name=role_name).first()
            if existing_role:
                role = existing_role
            else:
                role = Role(name=role_name, description=f"{role_name} role", is_system=True)
                db.add(role)
                db.flush()
                print(f"Created role: {role_name}")
            for code in perm_codes:
                exists = (
                    db.query(RolePermission)
                    .filter(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == perm_map[code].id,
                    )
                    .first()
                )
                if not exists:
                    db.add(RolePermission(role_id=role.id, permission_id=perm_map[code].id))
            roles[role_name] = role
        db.flush()

        # ── Admin user ─────────────────────────────────────────────────
        admin = db.query(User).filter_by(username="admin").first()
        if admin:
            admin.hashed_password = get_password_hash("Tuwaiq@Admin2026!")
            if admin.role_id is None:
                admin.role_id = roles["ADMIN"].id
                print("Assigned ADMIN role to admin user.")
            print("Updated admin password.")
        else:
            db.add(
                User(
                    username="admin",
                    hashed_password=get_password_hash("Tuwaiq@Admin2026!"),
                    role=RoleEnum.ADMIN,
                    role_id=roles["ADMIN"].id,
                )
            )
            print("Created admin user.")

        # ── Chart of Accounts ──────────────────────────────────────────
        for code, name, account_type in ACCOUNTS:
            existing = db.query(Account).filter_by(code=code).first()
            if existing:
                if not existing.is_system:
                    existing.is_system = True
                    print(f"Marked account {code} as system")
            else:
                db.add(
                    Account(
                        code=code,
                        name=name,
                        account_type=account_type,
                        is_system=True,
                    )
                )
                print(f"Created account {code} - {name}")

        # Default register
        if not db.query(Register).filter_by(name="Counter 1").first():
            db.add(Register(name="Counter 1", location="Main Store"))
            print("Created register: Counter 1")

        # Default warehouse
        main_store = db.query(Warehouse).filter_by(name="Main Store").first()
        if not main_store:
            main_store = Warehouse(name="Main Store")
            db.add(main_store)
            db.flush()
            print("Created warehouse: Main Store")

        # Link Counter 1 to Main Store if not linked
        counter1 = db.query(Register).filter_by(name="Counter 1").first()
        if counter1 and counter1.warehouse_id is None:
            counter1.warehouse_id = main_store.id
            print("Linked Counter 1 to Main Store warehouse")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
