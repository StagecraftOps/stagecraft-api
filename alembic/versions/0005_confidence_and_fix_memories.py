from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

def upgrade() -> None:

    op.add_column(
        'remediations',
        sa.Column('confidence_score', sa.Integer(), nullable=True),
    )
    op.add_column(
        'remediations',
        sa.Column('confidence_reasoning', sa.Text(), nullable=True),
    )

    op.create_table(
        'fix_memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=False),
        sa.Column('workflow_file', sa.String(512), nullable=False),
        sa.Column('failure_category', sa.String(64), nullable=False),
        sa.Column('root_cause', sa.Text(), nullable=False),
        sa.Column('original_yaml', sa.Text(), nullable=False),
        sa.Column('fixed_yaml', sa.Text(), nullable=False),
        sa.Column('remediation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('remediations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_fix_memories_org_login', 'fix_memories', ['org_login'])
    op.create_index('ix_fix_memories_failure_category', 'fix_memories', ['failure_category'])

def downgrade() -> None:
    op.drop_table('fix_memories')
    op.drop_column('remediations', 'confidence_reasoning')
    op.drop_column('remediations', 'confidence_score')
