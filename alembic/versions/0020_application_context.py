from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'application_contexts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=False),
        sa.Column('app_name', sa.String(255), nullable=True),
        sa.Column('language', sa.String(128), nullable=True),
        sa.Column('framework', sa.String(128), nullable=True),
        sa.Column('regulatory_scope', ARRAY(sa.String(64)), nullable=True),
        sa.Column('data_classification', sa.String(64), nullable=True),
        sa.Column('risk_tier', sa.String(32), nullable=True),
        sa.Column('team_owner', sa.String(255), nullable=True),
        sa.Column('security_contact', sa.String(255), nullable=True),
        sa.Column('source', sa.String(32), nullable=False, server_default='manual'),
        sa.Column('raw_content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('org_login', 'repo_name', name='uq_application_context_org_repo'),
    )
    op.create_index('ix_application_contexts_org_login', 'application_contexts', ['org_login'])
    op.create_index('ix_application_contexts_repo_name', 'application_contexts', ['repo_name'])

def downgrade() -> None:
    op.drop_index('ix_application_contexts_repo_name', table_name='application_contexts')
    op.drop_index('ix_application_contexts_org_login', table_name='application_contexts')
    op.drop_table('application_contexts')
