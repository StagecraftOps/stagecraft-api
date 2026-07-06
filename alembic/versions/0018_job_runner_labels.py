from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('job_runs', sa.Column('runner_labels', ARRAY(sa.Text()), nullable=True))
    op.add_column('job_runs', sa.Column('runner_group_name', sa.String(255), nullable=True))

def downgrade() -> None:
    op.drop_column('job_runs', 'runner_group_name')
    op.drop_column('job_runs', 'runner_labels')
