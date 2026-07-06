from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'optimization_recommendations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=False),
        sa.Column('workflow_file', sa.String(512), nullable=False),
        sa.Column('graph_id', UUID(as_uuid=True), sa.ForeignKey('graphs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recommendation_type', sa.String(32), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('proposed_yaml_diff', sa.Text(), nullable=True),
        sa.Column('estimated_time_savings_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confidence_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(32), nullable=False, server_default='proposed'),
        sa.Column('agent_trace', ARRAY(sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_optimization_recommendations_org_login', 'optimization_recommendations', ['org_login'])
    op.create_index('ix_optimization_recommendations_repo_name', 'optimization_recommendations', ['repo_name'])

    op.create_table(
        'simulation_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('recommendation_id', UUID(as_uuid=True), sa.ForeignKey('optimization_recommendations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('baseline_critical_path_seconds', sa.Integer(), nullable=False),
        sa.Column('simulated_critical_path_seconds', sa.Integer(), nullable=False),
        sa.Column('delta_seconds', sa.Integer(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_simulation_runs_recommendation_id', 'simulation_runs', ['recommendation_id'])

def downgrade() -> None:
    op.drop_index('ix_simulation_runs_recommendation_id', table_name='simulation_runs')
    op.drop_table('simulation_runs')

    op.drop_index('ix_optimization_recommendations_repo_name', table_name='optimization_recommendations')
    op.drop_index('ix_optimization_recommendations_org_login', table_name='optimization_recommendations')
    op.drop_table('optimization_recommendations')
