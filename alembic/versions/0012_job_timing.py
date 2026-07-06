from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'job_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('workflow_run_id', UUID(as_uuid=True), sa.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('github_job_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('job_name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(64), nullable=False),
        sa.Column('conclusion', sa.String(64), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('runner_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_job_runs_workflow_run_id', 'job_runs', ['workflow_run_id'])

    op.create_table(
        'job_steps',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('job_run_id', UUID(as_uuid=True), sa.ForeignKey('job_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('step_name', sa.String(512), nullable=False),
        sa.Column('status', sa.String(64), nullable=False),
        sa.Column('conclusion', sa.String(64), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
    )
    op.create_index('ix_job_steps_job_run_id', 'job_steps', ['job_run_id'])

    op.create_table(
        'critical_path_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('workflow_run_id', UUID(as_uuid=True), sa.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('total_duration_seconds', sa.Integer(), nullable=False),
        sa.Column('critical_path_job_ids', ARRAY(UUID(as_uuid=True)), nullable=False),
        sa.Column('longest_job_id', UUID(as_uuid=True), sa.ForeignKey('job_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table('critical_path_results')
    op.drop_index('ix_job_steps_job_run_id', table_name='job_steps')
    op.drop_table('job_steps')
    op.drop_index('ix_job_runs_workflow_run_id', table_name='job_runs')
    op.drop_table('job_runs')
