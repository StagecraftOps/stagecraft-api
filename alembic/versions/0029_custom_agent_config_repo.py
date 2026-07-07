from alembic import op
import sqlalchemy as sa

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        'custom_agent_configs',
        sa.Column('repo_name', sa.String(255), nullable=False, server_default=''),
    )
    op.drop_constraint('uq_custom_agent_config_org_key', 'custom_agent_configs', type_='unique')
    op.create_unique_constraint(
        'uq_custom_agent_config_org_key_repo', 'custom_agent_configs', ['org_id', 'agent_key', 'repo_name'],
    )

def downgrade() -> None:
    op.drop_constraint('uq_custom_agent_config_org_key_repo', 'custom_agent_configs', type_='unique')
    op.create_unique_constraint(
        'uq_custom_agent_config_org_key', 'custom_agent_configs', ['org_id', 'agent_key'],
    )
    op.drop_column('custom_agent_configs', 'repo_name')
