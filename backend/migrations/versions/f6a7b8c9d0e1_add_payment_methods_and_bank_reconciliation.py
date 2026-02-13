"""add_payment_methods_and_bank_reconciliation

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-11 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── PaymentMethod enum ────────────────────────────────────────────
    paymentmethod_enum = postgresql.ENUM(
        "CASH", "CARD", "BANK_TRANSFER",
        name="paymentmethod",
        create_type=False,
    )
    paymentmethod_enum.create(op.get_bind(), checkfirst=True)

    # ── sale_payments table ───────────────────────────────────────────
    op.create_table(
        "sale_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("journal_entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("payment_method", paymentmethod_enum, nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_sale_payment_amount_positive"),
    )
    op.create_index("ix_sale_payments_journal", "sale_payments", ["journal_entry_id"])
    op.create_index("ix_sale_payments_method", "sale_payments", ["payment_method"])
    op.create_index("ix_sale_payments_account", "sale_payments", ["account_id"])

    # ── ReconciliationStatus enum ─────────────────────────────────────
    reconciliation_enum = postgresql.ENUM(
        "UNMATCHED", "MATCHED", "RECONCILED",
        name="reconciliationstatus",
        create_type=False,
    )
    reconciliation_enum.create(op.get_bind(), checkfirst=True)

    # ── bank_statement_lines table ────────────────────────────────────
    op.create_table(
        "bank_statement_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("statement_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("status", reconciliation_enum, nullable=False, server_default="UNMATCHED"),
        sa.Column("matched_split_id", sa.Uuid(), sa.ForeignKey("transaction_splits.id"), nullable=True),
        sa.Column("reconciled_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bsl_statement_date", "bank_statement_lines", ["statement_date"])
    op.create_index("ix_bsl_status", "bank_statement_lines", ["status"])
    op.create_index("ix_bsl_matched_split", "bank_statement_lines", ["matched_split_id"])


def downgrade() -> None:
    op.drop_index("ix_bsl_matched_split", table_name="bank_statement_lines")
    op.drop_index("ix_bsl_status", table_name="bank_statement_lines")
    op.drop_index("ix_bsl_statement_date", table_name="bank_statement_lines")
    op.drop_table("bank_statement_lines")

    op.drop_index("ix_sale_payments_account", table_name="sale_payments")
    op.drop_index("ix_sale_payments_method", table_name="sale_payments")
    op.drop_index("ix_sale_payments_journal", table_name="sale_payments")
    op.drop_table("sale_payments")

    # Drop enum types
    postgresql.ENUM(name="reconciliationstatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="paymentmethod").drop(op.get_bind(), checkfirst=True)
