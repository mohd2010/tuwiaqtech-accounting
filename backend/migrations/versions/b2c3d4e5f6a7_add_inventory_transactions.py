"""add_inventory_transactions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-11 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create inventory_transactions table."""
    op.create_table(
        'inventory_transactions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column(
            'adjustment_type',
            sa.Enum('DAMAGE', 'THEFT', 'COUNT_ERROR', 'PROMOTION', name='adjustmenttype'),
            nullable=False,
        ),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('journal_entry_id', sa.Uuid(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inv_txn_product', 'inventory_transactions', ['product_id'])
    op.create_index('ix_inv_txn_created_at', 'inventory_transactions', ['created_at'])


def downgrade() -> None:
    """Drop inventory_transactions table."""
    op.drop_index('ix_inv_txn_created_at', table_name='inventory_transactions')
    op.drop_index('ix_inv_txn_product', table_name='inventory_transactions')
    op.drop_table('inventory_transactions')
    op.execute("DROP TYPE IF EXISTS adjustmenttype")
