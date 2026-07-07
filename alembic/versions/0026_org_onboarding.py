from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.alter_column('organizations', 'owner_id', nullable=True)
    op.add_column('organizations', sa.Column('installed_by_github_id', sa.BigInteger(), nullable=True))
    op.add_column('organizations', sa.Column('installed_by_login', sa.String(255), nullable=True))

    op.create_table(
        'org_repo_scope',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('org_id', 'repo_name', name='uq_org_repo_scope_org_repo'),
    )

    op.create_table(
        'org_sync_progress',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('runs_synced', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint('org_id', 'repo_name', name='uq_org_sync_progress_org_repo'),
    )

def downgrade() -> None:
    op.drop_table('org_sync_progress')
    op.drop_table('org_repo_scope')
    op.drop_column('organizations', 'installed_by_login')
    op.drop_column('organizations', 'installed_by_github_id')
    op.alter_column('organizations', 'owner_id', nullable=False)
