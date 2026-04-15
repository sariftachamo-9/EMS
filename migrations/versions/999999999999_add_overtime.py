"""Add overtime request model and overtime bypass

Revision ID: 999999999999
Revises: 237810bf6517
Create Date: 2026-04-12 13:14:51.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '999999999999'
down_revision = '237810bf6517'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('overtime_bypass_until', sa.DateTime(), nullable=True))
    
    op.create_table('overtime_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('overtime_type', sa.String(length=20), nullable=False),
        sa.Column('hours', sa.Float(), nullable=False),
        sa.Column('requested_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('applied_on', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], )
    )


def downgrade():
    op.drop_table('overtime_requests')
    
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('overtime_bypass_until')