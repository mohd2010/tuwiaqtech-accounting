"""add account lockout fields to users

Revision ID: da9f959568eb
Revises: m3b4c5d6e7f8
Create Date: 2026-02-13 04:25:52.407409

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'da9f959568eb'
down_revision: Union[str, Sequence[str], None] = 'm3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add account lockout fields to users table (NCA ECC 2-1)."""
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Remove account lockout fields."""
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
