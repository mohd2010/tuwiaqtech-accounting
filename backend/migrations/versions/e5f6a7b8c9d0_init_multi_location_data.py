"""init_multi_location_data

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-11 23:50:00.000000

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create "Main Store" warehouse
    warehouse_id = uuid4()
    conn.execute(
        sa.text(
            "INSERT INTO warehouses (id, name, address, is_active) "
            "VALUES (:id, :name, :address, true)"
        ),
        {"id": str(warehouse_id), "name": "Main Store", "address": None},
    )

    # 2. For each product with current_stock > 0, create warehouse_stock row
    products = conn.execute(
        sa.text("SELECT id, current_stock FROM products WHERE current_stock > 0")
    ).fetchall()

    for product_id, stock in products:
        conn.execute(
            sa.text(
                "INSERT INTO warehouse_stock (id, warehouse_id, product_id, quantity) "
                "VALUES (:id, :wid, :pid, :qty)"
            ),
            {
                "id": str(uuid4()),
                "wid": str(warehouse_id),
                "pid": str(product_id),
                "qty": stock,
            },
        )

    # 3. Link all registers to Main Store where warehouse_id is NULL
    conn.execute(
        sa.text(
            "UPDATE registers SET warehouse_id = :wid WHERE warehouse_id IS NULL"
        ),
        {"wid": str(warehouse_id)},
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Get Main Store warehouse id
    row = conn.execute(
        sa.text("SELECT id FROM warehouses WHERE name = 'Main Store' LIMIT 1")
    ).fetchone()
    if row:
        wid = str(row[0])
        # Unlink registers
        conn.execute(
            sa.text("UPDATE registers SET warehouse_id = NULL WHERE warehouse_id = :wid"),
            {"wid": wid},
        )
        # Remove warehouse_stock rows
        conn.execute(
            sa.text("DELETE FROM warehouse_stock WHERE warehouse_id = :wid"),
            {"wid": wid},
        )
        # Remove the warehouse
        conn.execute(
            sa.text("DELETE FROM warehouses WHERE id = :wid"),
            {"wid": wid},
        )
