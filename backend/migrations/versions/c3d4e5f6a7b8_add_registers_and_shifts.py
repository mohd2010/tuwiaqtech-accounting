"""add_registers_and_shifts

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-11 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create registers and shifts tables."""
    op.create_table(
        'registers',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    op.create_table(
        'shifts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('register_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('OPEN', 'CLOSED', name='shiftstatus'),
            nullable=False,
        ),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('opening_cash', sa.Numeric(precision=20, scale=4), nullable=False, server_default='0'),
        sa.Column('closing_cash_reported', sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column('expected_cash', sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column('discrepancy', sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['register_id'], ['registers.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_shifts_user', 'shifts', ['user_id'])
    op.create_index('ix_shifts_register', 'shifts', ['register_id'])
    op.create_index('ix_shifts_status', 'shifts', ['status'])
    op.create_index('ix_shifts_opened_at', 'shifts', ['opened_at'])


def downgrade() -> None:
    """Drop shifts and registers tables."""
    op.drop_index('ix_shifts_opened_at', table_name='shifts')
    op.drop_index('ix_shifts_status', table_name='shifts')
    op.drop_index('ix_shifts_register', table_name='shifts')
    op.drop_index('ix_shifts_user', table_name='shifts')
    op.drop_table('shifts')
    op.drop_table('registers')
    op.execute("DROP TYPE IF EXISTS shiftstatus")
