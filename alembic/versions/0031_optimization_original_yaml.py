from alembic import op
import sqlalchemy as sa

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('optimization_recommendations', sa.Column('original_yaml', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('optimization_recommendations', 'original_yaml')
