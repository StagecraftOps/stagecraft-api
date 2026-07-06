from alembic import op
import sqlalchemy as sa

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        'remediations',
        sa.Column('pr_raised_at', sa.DateTime(timezone=True), nullable=True),
    )

def downgrade() -> None:
    op.drop_column('remediations', 'pr_raised_at')
