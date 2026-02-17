"""Seed the database with an admin user and a standard chart of accounts.

Usage:
    python -m backend.scripts.seed
"""

from __future__ import annotations

from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models.accounting import Account, AccountType, RoleEnum, User
from backend.app.models.inventory import Warehouse
from backend.app.models.permission import Role  # noqa: F401 — needed for User.assigned_role relationship
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


def seed() -> None:
    db = SessionLocal()
    try:
        # Admin user
        admin = db.query(User).filter_by(username="admin").first()
        if admin:
            admin.hashed_password = get_password_hash("admin123")
            print("Updated admin password.")
        else:
            db.add(
                User(
                    username="admin",
                    hashed_password=get_password_hash("admin123"),
                    role=RoleEnum.ADMIN,
                )
            )
            print("Created admin user.")

        seed_codes: list[str] = []
        for code, name, account_type in ACCOUNTS:
            seed_codes.append(code)
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
