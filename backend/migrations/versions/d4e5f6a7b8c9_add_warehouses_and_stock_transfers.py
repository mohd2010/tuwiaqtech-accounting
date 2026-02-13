"""add_warehouses_and_stock_transfers

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-11 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Warehouses ─────────────────────────────────────────────────────────
    op.create_table(
        "warehouses",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_warehouses_name"),
    )

    # ── Warehouse Stock ────────────────────────────────────────────────────
    op.create_table(
        "warehouse_stock",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.CheckConstraint("quantity >= 0", name="ck_warehouse_stock_qty_non_negative"),
        sa.UniqueConstraint("warehouse_id", "product_id", name="uq_warehouse_product"),
    )
    op.create_index("ix_ws_warehouse", "warehouse_stock", ["warehouse_id"])
    op.create_index("ix_ws_product", "warehouse_stock", ["product_id"])

    # ── Stock Transfers ────────────────────────────────────────────────────
    transferstatus = postgresql.ENUM(
        "PENDING", "SHIPPED", "RECEIVED", "CANCELLED",
        name="transferstatus",
        create_type=True,
    )

    op.create_table(
        "stock_transfers",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("from_warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("to_warehouse_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            transferstatus,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["from_warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["to_warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.CheckConstraint(
            "from_warehouse_id != to_warehouse_id",
            name="ck_transfer_different_warehouses",
        ),
    )
    op.create_index("ix_transfers_status", "stock_transfers", ["status"])
    op.create_index("ix_transfers_created_at", "stock_transfers", ["created_at"])

    # ── Stock Transfer Items ───────────────────────────────────────────────
    op.create_table(
        "stock_transfer_items",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("transfer_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["transfer_id"], ["stock_transfers.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.CheckConstraint("quantity > 0", name="ck_transfer_item_qty_positive"),
    )

    # ── Add warehouse_id to registers ──────────────────────────────────────
    op.add_column(
        "registers",
        sa.Column("warehouse_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_registers_warehouse_id",
        "registers",
        "warehouses",
        ["warehouse_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_registers_warehouse_id", "registers", type_="foreignkey")
    op.drop_column("registers", "warehouse_id")
    op.drop_table("stock_transfer_items")
    op.drop_index("ix_transfers_created_at", table_name="stock_transfers")
    op.drop_index("ix_transfers_status", table_name="stock_transfers")
    op.drop_table("stock_transfers")
    postgresql.ENUM(name="transferstatus").drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_ws_product", table_name="warehouse_stock")
    op.drop_index("ix_ws_warehouse", table_name="warehouse_stock")
    op.drop_table("warehouse_stock")
    op.drop_table("warehouses")
