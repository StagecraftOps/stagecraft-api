from alembic import op
import sqlalchemy as sa

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('remediations', sa.Column('likely_code_level', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('remediations', sa.Column('code_level_reasoning', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('remediations', 'code_level_reasoning')
    op.drop_column('remediations', 'likely_code_level')
