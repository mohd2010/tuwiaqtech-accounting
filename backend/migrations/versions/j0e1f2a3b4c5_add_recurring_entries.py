"""Add recurring entries tables.

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-02-12 12:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "j0e1f2a3b4c5"
down_revision: Union[str, None] = "i9d0e1f2a3b4"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Enums are created automatically by create_table via sa.Enum()
    op.create_table(
        "recurring_entries",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_prefix", sa.String(50), nullable=True),
        sa.Column(
            "frequency",
            sa.Enum(
                "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUALLY",
                name="recurringfrequency",
            ),
            nullable=False,
        ),
        sa.Column("next_run_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "PAUSED", name="recurringstatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("last_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_posted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_recurring_entries_next_run", "recurring_entries", ["next_run_date"])
    op.create_index("ix_recurring_entries_status", "recurring_entries", ["status"])
    op.create_index("ix_recurring_entries_created_by", "recurring_entries", ["created_by"])

    op.create_table(
        "recurring_entry_splits",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "recurring_entry_id",
            sa.Uuid(),
            sa.ForeignKey("recurring_entries.id"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id"),
            nullable=False,
        ),
        sa.Column(
            "debit_amount",
            sa.Numeric(precision=20, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "credit_amount",
            sa.Numeric(precision=20, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(credit_amount > 0 AND debit_amount = 0)",
            name="ck_recurring_split_debit_xor_credit",
        ),
        sa.CheckConstraint("debit_amount >= 0", name="ck_recurring_split_debit_non_negative"),
        sa.CheckConstraint("credit_amount >= 0", name="ck_recurring_split_credit_non_negative"),
    )
    op.create_index("ix_recurring_splits_entry", "recurring_entry_splits", ["recurring_entry_id"])


def downgrade() -> None:
    op.drop_index("ix_recurring_splits_entry", table_name="recurring_entry_splits")
    op.drop_table("recurring_entry_splits")
    op.drop_index("ix_recurring_entries_created_by", table_name="recurring_entries")
    op.drop_index("ix_recurring_entries_status", table_name="recurring_entries")
    op.drop_index("ix_recurring_entries_next_run", table_name="recurring_entries")
    op.drop_table("recurring_entries")

    sa.Enum(name="recurringstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="recurringfrequency").drop(op.get_bind(), checkfirst=True)
