"""Add ZATCA onboarding fields: csr_pem, compliance_request_id, onboarding_status

Revision ID: m3b4c5d6e7f8
Revises: l2a3b4c5d6e7
Create Date: 2026-02-12

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m3b4c5d6e7f8"
down_revision: Union[str, None] = "l2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("csr_pem", sa.LargeBinary(), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("compliance_request_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("onboarding_status", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "onboarding_status")
    op.drop_column("organizations", "compliance_request_id")
    op.drop_column("organizations", "csr_pem")
