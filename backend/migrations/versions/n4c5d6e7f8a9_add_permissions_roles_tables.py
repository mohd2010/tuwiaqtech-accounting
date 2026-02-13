"""add permissions, roles, and role_permissions tables

Revision ID: n4c5d6e7f8a9
Revises: da9f959568eb
Create Date: 2026-02-13 12:00:00.000000

"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "n4c5d6e7f8a9"
down_revision: Union[str, None] = "da9f959568eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ─── Permission definitions ─────────────────────────────────────────────────

PERMISSIONS: list[dict[str, str]] = [
    # accounting
    {"code": "account:read", "description": "View chart of accounts", "category": "accounting"},
    {"code": "account:write", "description": "Create/update/delete accounts", "category": "accounting"},
    {"code": "journal:read", "description": "View journal entries", "category": "accounting"},
    {"code": "journal:write", "description": "Create journal entries", "category": "accounting"},
    # pos
    {"code": "pos:sale", "description": "Process POS sales", "category": "pos"},
    {"code": "pos:shift", "description": "Open/close shifts", "category": "pos"},
    {"code": "pos:shift_list", "description": "View all shifts", "category": "pos"},
    # inventory
    {"code": "inventory:read", "description": "View products and categories", "category": "inventory"},
    {"code": "inventory:write", "description": "Create/update products and categories", "category": "inventory"},
    {"code": "inventory:adjust", "description": "Create stock adjustments", "category": "inventory"},
    # warehouse
    {"code": "warehouse:read", "description": "View warehouses and stock", "category": "warehouse"},
    {"code": "warehouse:write", "description": "Manage warehouses and transfers", "category": "warehouse"},
    # returns
    {"code": "returns:process", "description": "Process sales returns", "category": "returns"},
    # expenses
    {"code": "expense:read", "description": "View expenses", "category": "expenses"},
    {"code": "expense:write", "description": "Record expenses", "category": "expenses"},
    # sales
    {"code": "sales:read", "description": "View sales history", "category": "sales"},
    {"code": "quote:read", "description": "View quotes", "category": "sales"},
    {"code": "quote:write", "description": "Create/manage quotes", "category": "sales"},
    # suppliers
    {"code": "supplier:read", "description": "View suppliers", "category": "suppliers"},
    {"code": "supplier:write", "description": "Manage suppliers", "category": "suppliers"},
    {"code": "purchase:read", "description": "View purchase orders", "category": "suppliers"},
    {"code": "purchase:write", "description": "Manage purchase orders and returns", "category": "suppliers"},
    # reports
    {"code": "report:read", "description": "View financial reports", "category": "reports"},
    {"code": "report:export", "description": "Export reports to Excel/PDF", "category": "reports"},
    # banking
    {"code": "banking:read", "description": "View bank reconciliation", "category": "banking"},
    {"code": "banking:write", "description": "Manage bank reconciliation", "category": "banking"},
    # invoices
    {"code": "invoice:read", "description": "View credit invoices", "category": "invoices"},
    {"code": "invoice:write", "description": "Create credit invoices and payments", "category": "invoices"},
    # admin
    {"code": "fiscal:close", "description": "Close fiscal year", "category": "admin"},
    {"code": "recurring:read", "description": "View recurring entries", "category": "admin"},
    {"code": "recurring:write", "description": "Manage recurring entries", "category": "admin"},
    {"code": "user:read", "description": "View user list", "category": "admin"},
    {"code": "user:manage", "description": "Create/update/delete users", "category": "admin"},
    {"code": "organization:read", "description": "View organization settings", "category": "admin"},
    {"code": "organization:write", "description": "Update organization settings", "category": "admin"},
    # zatca
    {"code": "einvoice:read", "description": "View e-invoices", "category": "zatca"},
    {"code": "einvoice:write", "description": "Submit e-invoices to ZATCA", "category": "zatca"},
    {"code": "audit:read", "description": "View audit logs", "category": "zatca"},
]

ALL_CODES = [p["code"] for p in PERMISSIONS]

ADMIN_CODES = ALL_CODES  # Admin gets everything

ACCOUNTANT_CODES = [
    c for c in ALL_CODES
    if c not in {
        "pos:sale", "pos:shift", "returns:process",
        "user:read", "user:manage",
        "organization:write", "fiscal:close",
        "einvoice:write",
    }
]

CASHIER_CODES = [
    "pos:sale", "pos:shift", "inventory:read", "sales:read",
    "returns:process", "account:read", "warehouse:read",
    "einvoice:read",
]


def upgrade() -> None:
    # 1. Create permissions table
    op.create_table(
        "permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
    )

    # 2. Create roles table
    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 3. Create role_permissions junction table
    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("permission_id", UUID(as_uuid=True), sa.ForeignKey("permissions.id"), primary_key=True),
    )

    # 4. Add role_id FK to users
    op.add_column("users", sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=True))

    # 5. Seed permissions
    conn = op.get_bind()
    perm_ids: dict[str, uuid.UUID] = {}
    for p in PERMISSIONS:
        pid = uuid.uuid4()
        perm_ids[p["code"]] = pid
        conn.execute(
            sa.text("INSERT INTO permissions (id, code, description, category) VALUES (:id, :code, :desc, :cat)"),
            {"id": pid, "code": p["code"], "desc": p["description"], "cat": p["category"]},
        )

    # 6. Seed roles
    role_ids: dict[str, uuid.UUID] = {}
    for role_name, description in [
        ("ADMIN", "Full system access"),
        ("ACCOUNTANT", "Accounting and reporting access"),
        ("CASHIER", "POS and sales access"),
    ]:
        rid = uuid.uuid4()
        role_ids[role_name] = rid
        conn.execute(
            sa.text("INSERT INTO roles (id, name, description, is_system) VALUES (:id, :name, :desc, true)"),
            {"id": rid, "name": role_name, "desc": description},
        )

    # 7. Seed role-permission mappings
    for role_name, codes in [
        ("ADMIN", ADMIN_CODES),
        ("ACCOUNTANT", ACCOUNTANT_CODES),
        ("CASHIER", CASHIER_CODES),
    ]:
        for code in codes:
            conn.execute(
                sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"),
                {"rid": role_ids[role_name], "pid": perm_ids[code]},
            )

    # 8. Data migration: set role_id on existing users based on their RoleEnum
    for role_name in ("ADMIN", "ACCOUNTANT", "CASHIER"):
        conn.execute(
            sa.text("UPDATE users SET role_id = :rid WHERE role = :role_name"),
            {"rid": role_ids[role_name], "role_name": role_name},
        )


def downgrade() -> None:
    op.drop_column("users", "role_id")
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_table("permissions")
