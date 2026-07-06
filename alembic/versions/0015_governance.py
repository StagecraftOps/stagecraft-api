from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'governance_documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('doc_type', sa.String(32), nullable=False),
        sa.Column('title', sa.String(512), nullable=False),
        sa.Column('source_filename', sa.String(512), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('structured_requirements', JSONB(), nullable=True),
        sa.Column('uploaded_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_governance_documents_org_login', 'governance_documents', ['org_login'])

    op.create_table(
        'compliance_findings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=False),
        sa.Column('workflow_file', sa.String(512), nullable=False),
        sa.Column('governance_document_id', UUID(as_uuid=True), sa.ForeignKey('governance_documents.id', ondelete='CASCADE'), nullable=True),
        sa.Column('requirement_id', sa.String(128), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('finding_detail', sa.Text(), nullable=False),
        sa.Column('remediation_suggestion', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(32), nullable=False, server_default='medium'),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_compliance_findings_org_login', 'compliance_findings', ['org_login'])
    op.create_index('ix_compliance_findings_repo_name', 'compliance_findings', ['repo_name'])

def downgrade() -> None:
    op.drop_index('ix_compliance_findings_repo_name', table_name='compliance_findings')
    op.drop_index('ix_compliance_findings_org_login', table_name='compliance_findings')
    op.drop_table('compliance_findings')

    op.drop_index('ix_governance_documents_org_login', table_name='governance_documents')
    op.drop_table('governance_documents')
