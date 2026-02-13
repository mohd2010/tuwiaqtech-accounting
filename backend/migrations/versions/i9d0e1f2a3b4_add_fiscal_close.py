"""Add fiscal_closes table and Retained Earnings account

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-02-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "i9d0e1f2a3b4"
down_revision: Union[str, None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create fiscal_closes table
    op.create_table(
        "fiscal_closes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("close_date", sa.Date(), nullable=False),
        sa.Column("closing_entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("closed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_year", name="uq_fiscal_closes_year"),
    )
    op.create_index("ix_fiscal_closes_year", "fiscal_closes", ["fiscal_year"])

    # 2. Seed Retained Earnings account (3000, EQUITY) if not exists
    op.execute(
        """
        INSERT INTO accounts (id, code, name, account_type, is_active, is_system, created_at)
        VALUES (gen_random_uuid(), '3000', 'Retained Earnings', 'EQUITY', true, true, now())
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_fiscal_closes_year", table_name="fiscal_closes")
    op.drop_table("fiscal_closes")
    # Note: We don't remove the Retained Earnings account in downgrade
    # as it may have transaction history
