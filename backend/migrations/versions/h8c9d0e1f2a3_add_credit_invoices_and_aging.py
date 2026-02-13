"""add_credit_invoices_and_aging

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-02-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "h8c9d0e1f2a3"
down_revision: Union[str, None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create InvoiceStatus enum
    invoice_status_enum = postgresql.ENUM(
        "OPEN", "PARTIAL", "PAID", name="invoicestatus", create_type=False
    )
    invoice_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Add columns to customers
    op.add_column(
        "customers",
        sa.Column("credit_limit", sa.Numeric(precision=20, scale=4), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column(
            "payment_terms_days",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )

    # 3. Create credit_invoices table
    op.create_table(
        "credit_invoices",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id"),
            nullable=False,
        ),
        sa.Column(
            "journal_entry_id",
            sa.Uuid(),
            sa.ForeignKey("journal_entries.id"),
            nullable=False,
        ),
        sa.Column(
            "invoice_number",
            sa.String(50),
            nullable=False,
            unique=True,
        ),
        sa.Column("invoice_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "total_amount",
            sa.Numeric(precision=20, scale=4),
            nullable=False,
        ),
        sa.Column(
            "amount_paid",
            sa.Numeric(precision=20, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column("status", invoice_status_enum, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("total_amount > 0", name="ck_credit_invoice_total_positive"),
        sa.CheckConstraint("amount_paid >= 0", name="ck_credit_invoice_paid_non_negative"),
    )
    op.create_index("ix_credit_invoices_customer", "credit_invoices", ["customer_id"])
    op.create_index("ix_credit_invoices_status", "credit_invoices", ["status"])
    op.create_index("ix_credit_invoices_due_date", "credit_invoices", ["due_date"])

    # 4. Create invoice_payments table
    op.create_table(
        "invoice_payments",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "invoice_id",
            sa.Uuid(),
            sa.ForeignKey("credit_invoices.id"),
            nullable=False,
        ),
        sa.Column(
            "journal_entry_id",
            sa.Uuid(),
            sa.ForeignKey("journal_entries.id"),
            nullable=False,
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=20, scale=4),
            nullable=False,
        ),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("amount > 0", name="ck_invoice_payment_amount_positive"),
    )
    op.create_index("ix_invoice_payments_invoice", "invoice_payments", ["invoice_id"])

    # 5. Seed Accounts Receivable (1300) and Supplier Payables (2100)
    op.execute(
        """
        INSERT INTO accounts (id, code, name, account_type, is_active, is_system, created_at)
        VALUES (
            gen_random_uuid(),
            '1300',
            'Accounts Receivable',
            'ASSET',
            true,
            true,
            now()
        )
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO accounts (id, code, name, account_type, is_active, is_system, created_at)
        VALUES (
            gen_random_uuid(),
            '2100',
            'Supplier Payables',
            'LIABILITY',
            true,
            true,
            now()
        )
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM accounts WHERE code IN ('1300', '2100') AND is_system = true"
    )
    op.drop_index("ix_invoice_payments_invoice", table_name="invoice_payments")
    op.drop_table("invoice_payments")
    op.drop_index("ix_credit_invoices_due_date", table_name="credit_invoices")
    op.drop_index("ix_credit_invoices_status", table_name="credit_invoices")
    op.drop_index("ix_credit_invoices_customer", table_name="credit_invoices")
    op.drop_table("credit_invoices")
    op.drop_column("customers", "payment_terms_days")
    op.drop_column("customers", "credit_limit")
    postgresql.ENUM(name="invoicestatus").drop(op.get_bind(), checkfirst=True)
