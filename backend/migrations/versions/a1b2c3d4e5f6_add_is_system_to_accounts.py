"""add_is_system_to_accounts

Revision ID: a1b2c3d4e5f6
Revises: 5964ccfd67f3
Create Date: 2026-02-11 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5964ccfd67f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_system column to accounts table."""
    op.add_column('accounts', sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    """Remove is_system column from accounts table."""
    op.drop_column('accounts', 'is_system')
