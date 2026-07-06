from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'agent_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=True),
        sa.Column('agent_name', sa.String(128), nullable=False),
        sa.Column('github_run_id', sa.String(64), nullable=True),
        sa.Column('outcome', sa.String(64), nullable=False, server_default='success'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('gaps_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prs_opened', ARRAY(sa.Text()), nullable=True),
        sa.Column('artifacts', ARRAY(sa.Text()), nullable=True),
        sa.Column('conditions_evaluated', JSONB(), nullable=True),
        sa.Column('evidence', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_agent_runs_org_login', 'agent_runs', ['org_login'])
    op.create_index('ix_agent_runs_repo_name', 'agent_runs', ['repo_name'])
    op.create_index('ix_agent_runs_agent_name', 'agent_runs', ['agent_name'])
    op.create_index('ix_agent_runs_outcome', 'agent_runs', ['outcome'])
    op.create_index('ix_agent_runs_created_at', 'agent_runs', ['created_at'])

def downgrade() -> None:
    op.drop_index('ix_agent_runs_created_at', table_name='agent_runs')
    op.drop_index('ix_agent_runs_outcome', table_name='agent_runs')
    op.drop_index('ix_agent_runs_agent_name', table_name='agent_runs')
    op.drop_index('ix_agent_runs_repo_name', table_name='agent_runs')
    op.drop_index('ix_agent_runs_org_login', table_name='agent_runs')
    op.drop_table('agent_runs')
