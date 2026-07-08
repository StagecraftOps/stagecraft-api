from alembic import op
import sqlalchemy as sa

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('optimization_recommendations', sa.Column('pr_url', sa.String(512), nullable=True))
    op.add_column('optimization_recommendations', sa.Column('pr_number', sa.Integer(), nullable=True))
    op.add_column('optimization_recommendations', sa.Column('pr_branch', sa.String(255), nullable=True))

def downgrade() -> None:
    op.drop_column('optimization_recommendations', 'pr_branch')
    op.drop_column('optimization_recommendations', 'pr_number')
    op.drop_column('optimization_recommendations', 'pr_url')
