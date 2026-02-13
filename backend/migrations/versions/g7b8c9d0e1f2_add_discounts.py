"""add_discounts

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the DiscountType enum
    discount_type_enum = postgresql.ENUM(
        "PERCENTAGE", "FIXED_AMOUNT", name="discounttype", create_type=False
    )
    discount_type_enum.create(op.get_bind(), checkfirst=True)

    # Create sale_discounts table
    op.create_table(
        "sale_discounts",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "journal_entry_id",
            sa.Uuid(),
            sa.ForeignKey("journal_entries.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "discount_type",
            discount_type_enum,
            nullable=False,
        ),
        sa.Column(
            "discount_value",
            sa.Numeric(precision=20, scale=4),
            nullable=False,
        ),
        sa.Column(
            "discount_amount",
            sa.Numeric(precision=20, scale=4),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("discount_value > 0", name="ck_sale_discount_value_positive"),
        sa.CheckConstraint("discount_amount > 0", name="ck_sale_discount_amount_positive"),
    )
    op.create_index("ix_sale_discounts_journal", "sale_discounts", ["journal_entry_id"])

    # Seed the Sales Discounts contra-revenue account (4100)
    op.execute(
        """
        INSERT INTO accounts (id, code, name, account_type, is_active, is_system, created_at)
        VALUES (
            gen_random_uuid(),
            '4100',
            'Sales Discounts',
            'REVENUE',
            true,
            true,
            now()
        )
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM accounts WHERE code = '4100' AND is_system = true")
    op.drop_index("ix_sale_discounts_journal", table_name="sale_discounts")
    op.drop_table("sale_discounts")
    postgresql.ENUM(name="discounttype").drop(op.get_bind(), checkfirst=True)
