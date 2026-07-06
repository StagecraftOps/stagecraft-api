from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('organizations', sa.Column('installation_id', sa.BigInteger(), nullable=True))
    op.create_index('ix_organizations_installation_id', 'organizations', ['installation_id'])

def downgrade() -> None:
    op.drop_index('ix_organizations_installation_id', table_name='organizations')
    op.drop_column('organizations', 'installation_id')
