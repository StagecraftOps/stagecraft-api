from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'workflow_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_yaml', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_workflow_templates_org_login', 'workflow_templates', ['org_login'])

    op.create_table(
        'template_diffs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=False),
        sa.Column('workflow_file', sa.String(512), nullable=False),
        sa.Column('template_id', UUID(as_uuid=True), sa.ForeignKey('workflow_templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('diff_summary', JSONB(), nullable=False),
        sa.Column('adoption_score', sa.Integer(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_template_diffs_org_login', 'template_diffs', ['org_login'])
    op.create_index('ix_template_diffs_repo_name', 'template_diffs', ['repo_name'])

    op.create_table(
        'pattern_clusters',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('pattern_hash', sa.String(64), nullable=False),
        sa.Column('pattern_signature', JSONB(), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), nullable=False),
        sa.Column('example_workflow_files', ARRAY(sa.Text()), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_pattern_clusters_org_login', 'pattern_clusters', ['org_login'])
    op.create_index('ix_pattern_clusters_pattern_hash', 'pattern_clusters', ['pattern_hash'])

def downgrade() -> None:
    op.drop_index('ix_pattern_clusters_pattern_hash', table_name='pattern_clusters')
    op.drop_index('ix_pattern_clusters_org_login', table_name='pattern_clusters')
    op.drop_table('pattern_clusters')

    op.drop_index('ix_template_diffs_repo_name', table_name='template_diffs')
    op.drop_index('ix_template_diffs_org_login', table_name='template_diffs')
    op.drop_table('template_diffs')

    op.drop_index('ix_workflow_templates_org_login', table_name='workflow_templates')
    op.drop_table('workflow_templates')
