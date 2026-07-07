from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'custom_agent_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('org_login', sa.String(255), nullable=False, index=True),
        sa.Column('agent_key', sa.String(128), nullable=False, index=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('skill_files', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint('org_id', 'agent_key', name='uq_custom_agent_config_org_key'),
    )

def downgrade() -> None:
    op.drop_table('custom_agent_configs')
