from alembic import op
import sqlalchemy as sa

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('remediations', sa.Column('original_yaml', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('remediations', 'original_yaml')
