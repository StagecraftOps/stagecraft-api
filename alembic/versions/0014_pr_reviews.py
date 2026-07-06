from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'pr_reviews',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('pr_url', sa.String(1024), nullable=False, server_default=''),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('findings', ARRAY(sa.Text()), nullable=True),
        sa.Column('review_summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(64), nullable=False, server_default='pending'),
        sa.Column('agent_trace', ARRAY(sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_pr_reviews_org_login', 'pr_reviews', ['org_login'])
    op.create_index('ix_pr_reviews_repo_name', 'pr_reviews', ['repo_name'])
    op.create_index('ix_pr_reviews_status', 'pr_reviews', ['status'])

def downgrade() -> None:
    op.drop_index('ix_pr_reviews_status', table_name='pr_reviews')
    op.drop_index('ix_pr_reviews_repo_name', table_name='pr_reviews')
    op.drop_index('ix_pr_reviews_org_login', table_name='pr_reviews')
    op.drop_table('pr_reviews')
