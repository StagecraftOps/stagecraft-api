from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('remediations', sa.Column('security_risk_score', sa.Integer(), nullable=True))
    op.add_column('remediations', sa.Column('security_findings', ARRAY(sa.Text()), nullable=True))
    op.add_column('remediations', sa.Column('pr_title', sa.String(512), nullable=True))
    op.add_column('remediations', sa.Column('pr_description', sa.Text(), nullable=True))
    op.add_column('remediations', sa.Column('agent_trace', ARRAY(sa.Text()), nullable=True))

def downgrade() -> None:
    op.drop_column('remediations', 'agent_trace')
    op.drop_column('remediations', 'pr_description')
    op.drop_column('remediations', 'pr_title')
    op.drop_column('remediations', 'security_findings')
    op.drop_column('remediations', 'security_risk_score')
