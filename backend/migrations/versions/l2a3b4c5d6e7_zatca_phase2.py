"""ZATCA Phase 2: organizations, einvoices, icv_counter, customer address

Revision ID: l2a3b4c5d6e7
Revises: k1f2a3b4c5d6
Create Date: 2026-02-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l2a3b4c5d6e7"
down_revision: Union[str, None] = "k1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create enums ─────────────────────────────────────────────────────
    invoicetypecode = postgresql.ENUM(
        "388", "381", "383", name="invoicetypecode", create_type=False
    )
    invoicetypecode.create(op.get_bind(), checkfirst=True)

    invoicesubtype = postgresql.ENUM(
        "0100000", "0200000", name="invoicesubtype", create_type=False
    )
    invoicesubtype.create(op.get_bind(), checkfirst=True)

    zatcasubmissionstatus = postgresql.ENUM(
        "PENDING", "SUBMITTED", "CLEARED", "REPORTED", "REJECTED", "WARNING",
        name="zatcasubmissionstatus", create_type=False,
    )
    zatcasubmissionstatus.create(op.get_bind(), checkfirst=True)

    # ── Create organizations table ───────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("vat_number", sa.String(15), nullable=False),
        sa.Column("additional_id", sa.String(20), nullable=True),
        sa.Column("cr_number", sa.String(20), nullable=True),
        sa.Column("street", sa.String(255), nullable=False),
        sa.Column("building_number", sa.String(4), nullable=False),
        sa.Column("city", sa.String(255), nullable=False),
        sa.Column("district", sa.String(255), nullable=False),
        sa.Column("postal_code", sa.String(5), nullable=False),
        sa.Column("province", sa.String(255), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="SA"),
        sa.Column("private_key_pem", sa.LargeBinary(), nullable=True),
        sa.Column("certificate_pem", sa.LargeBinary(), nullable=True),
        sa.Column("csid", sa.Text(), nullable=True),
        sa.Column("certificate_serial", sa.String(255), nullable=True),
        sa.Column("is_production", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("zatca_api_base_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Create einvoices table ───────────────────────────────────────────
    op.create_table(
        "einvoices",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("journal_entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("credit_note_id", sa.Uuid(), sa.ForeignKey("credit_notes.id"), nullable=True),
        sa.Column("invoice_uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("icv", sa.Integer(), nullable=False, unique=True),
        sa.Column("type_code", invoicetypecode, nullable=False),
        sa.Column("sub_type", invoicesubtype, nullable=False),
        sa.Column("invoice_hash", sa.String(64), nullable=False),
        sa.Column("previous_invoice_hash", sa.String(64), nullable=False),
        sa.Column("xml_content", sa.LargeBinary(), nullable=False),
        sa.Column("qr_code", sa.Text(), nullable=False),
        sa.Column("total_excluding_vat", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("total_vat", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("total_including_vat", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("buyer_name", sa.String(255), nullable=True),
        sa.Column("buyer_vat_number", sa.String(15), nullable=True),
        sa.Column("submission_status", zatcasubmissionstatus, nullable=False, server_default="PENDING"),
        sa.Column("zatca_request_id", sa.String(255), nullable=True),
        sa.Column("zatca_clearance_status", sa.String(50), nullable=True),
        sa.Column("zatca_reporting_status", sa.String(50), nullable=True),
        sa.Column("zatca_warnings", postgresql.JSONB(), nullable=True),
        sa.Column("zatca_errors", postgresql.JSONB(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supply_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_einvoices_invoice_number", "einvoices", ["invoice_number"])
    op.create_index("ix_einvoices_submission_status", "einvoices", ["submission_status"])
    op.create_index("ix_einvoices_issue_date", "einvoices", ["issue_date"])
    op.create_index("ix_einvoices_journal_entry_id", "einvoices", ["journal_entry_id"])

    # ── Create icv_counter table ─────────────────────────────────────────
    op.create_table(
        "icv_counter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    # Seed the singleton row
    op.execute("INSERT INTO icv_counter (id, current_value) VALUES (1, 0)")

    # ── Add address columns to customers ─────────────────────────────────
    op.add_column("customers", sa.Column("street", sa.String(255), nullable=True))
    op.add_column("customers", sa.Column("building_number", sa.String(4), nullable=True))
    op.add_column("customers", sa.Column("city", sa.String(255), nullable=True))
    op.add_column("customers", sa.Column("district", sa.String(255), nullable=True))
    op.add_column("customers", sa.Column("postal_code", sa.String(5), nullable=True))
    op.add_column("customers", sa.Column("country_code", sa.String(2), nullable=True, server_default="SA"))
    op.add_column("customers", sa.Column("additional_id", sa.String(20), nullable=True))


def downgrade() -> None:
    # ── Drop customer address columns ────────────────────────────────────
    op.drop_column("customers", "additional_id")
    op.drop_column("customers", "country_code")
    op.drop_column("customers", "postal_code")
    op.drop_column("customers", "district")
    op.drop_column("customers", "city")
    op.drop_column("customers", "building_number")
    op.drop_column("customers", "street")

    # ── Drop tables ──────────────────────────────────────────────────────
    op.drop_table("icv_counter")
    op.drop_index("ix_einvoices_journal_entry_id", table_name="einvoices")
    op.drop_index("ix_einvoices_issue_date", table_name="einvoices")
    op.drop_index("ix_einvoices_submission_status", table_name="einvoices")
    op.drop_index("ix_einvoices_invoice_number", table_name="einvoices")
    op.drop_table("einvoices")
    op.drop_table("organizations")

    # ── Drop enums ───────────────────────────────────────────────────────
    sa.Enum(name="zatcasubmissionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="invoicesubtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="invoicetypecode").drop(op.get_bind(), checkfirst=True)
