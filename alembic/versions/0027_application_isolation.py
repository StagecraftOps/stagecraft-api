from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None

# Repo-scoped domain tables that gain a first-class application_id.
_APP_SCOPED_TABLES = [
    'workflow_runs',
    'remediations',
    'application_contexts',
    'vulnerability_findings',
    'pr_reviews',
    'agent_runs',
    'graphs',
    'compliance_findings',
    'template_diffs',
    'pattern_clusters',
    'optimization_recommendations',
    'job_runs',
    'fix_memories',
    'chat_messages',
]

def upgrade() -> None:
    op.create_table(
        'applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('org_login', sa.String(255), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint('org_id', 'slug', name='uq_application_org_slug'),
    )

    op.create_table(
        'application_repos',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('org_login', sa.String(255), nullable=False, index=True),
        sa.Column('repo_name', sa.String(255), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('application_id', 'repo_name', name='uq_application_repo'),
        sa.UniqueConstraint('org_id', 'repo_name', name='uq_application_repo_org_repo'),
    )

    for table in _APP_SCOPED_TABLES:
        op.add_column(table, sa.Column('application_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_index(f'ix_{table}_application_id', table, ['application_id'])

def downgrade() -> None:
    for table in _APP_SCOPED_TABLES:
        op.drop_index(f'ix_{table}_application_id', table_name=table)
        op.drop_column(table, 'application_id')
    op.drop_table('application_repos')
    op.drop_table('applications')
