"""Add purchase returns tables.

Revision ID: k1f2a3b4c5d6
Revises: j0e1f2a3b4c5
Create Date: 2026-02-12 14:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "k1f2a3b4c5d6"
down_revision: Union[str, None] = "j0e1f2a3b4c5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # prstatus enum is auto-created by create_table (new type)
    # itemcondition enum already exists from credit_notes migration → use raw SQL column

    op.create_table(
        "purchase_returns",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column("po_id", sa.Uuid(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("return_number", sa.String(100), unique=True, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "ISSUED", name="prstatus"),
            nullable=False,
        ),
        sa.Column("total_amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("journal_entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_purchase_returns_po", "purchase_returns", ["po_id"])
    op.create_index("ix_purchase_returns_status", "purchase_returns", ["status"])
    op.create_index("ix_purchase_returns_created_at", "purchase_returns", ["created_at"])

    # For purchase_return_items, use raw SQL for the condition column
    # to avoid SQLAlchemy trying to re-create the existing itemcondition enum
    op.execute("""
        CREATE TABLE purchase_return_items (
            id UUID NOT NULL PRIMARY KEY,
            purchase_return_id UUID NOT NULL REFERENCES purchase_returns(id),
            product_id UUID NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL,
            unit_cost NUMERIC(20, 4) NOT NULL,
            condition itemcondition NOT NULL
        )
    """)
    op.create_index("ix_pr_items_pr", "purchase_return_items", ["purchase_return_id"])
    op.create_index("ix_pr_items_product", "purchase_return_items", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_pr_items_product", table_name="purchase_return_items")
    op.drop_index("ix_pr_items_pr", table_name="purchase_return_items")
    op.drop_table("purchase_return_items")
    op.drop_index("ix_purchase_returns_created_at", table_name="purchase_returns")
    op.drop_index("ix_purchase_returns_status", table_name="purchase_returns")
    op.drop_index("ix_purchase_returns_po", table_name="purchase_returns")
    op.drop_table("purchase_returns")

    op.execute("DROP TYPE IF EXISTS prstatus")
