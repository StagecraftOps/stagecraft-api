from alembic import op
import sqlalchemy as sa

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('application_contexts', sa.Column('notes', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('application_contexts', 'notes')
