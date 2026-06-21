"""Add failure_category to remediations

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-21

"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'remediations',
        sa.Column('failure_category', sa.String(64), nullable=True),
    )
    op.create_index('ix_remediations_failure_category', 'remediations', ['failure_category'])


def downgrade() -> None:
    op.drop_index('ix_remediations_failure_category', table_name='remediations')
    op.drop_column('remediations', 'failure_category')
