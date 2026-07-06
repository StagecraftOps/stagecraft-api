from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'graphs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_login', sa.String(255), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=True),
        sa.Column('graph_type', sa.String(32), nullable=False),
        sa.Column('ref', sa.String(255), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('node_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('edge_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.String(2048), nullable=True),
        sa.Column('built_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_graphs_org_login', 'graphs', ['org_login'])
    op.create_index('ix_graphs_repo_name', 'graphs', ['repo_name'])
    op.create_index('ix_graphs_graph_type', 'graphs', ['graph_type'])
    op.create_index('ix_graphs_status', 'graphs', ['status'])

    op.create_table(
        'graph_nodes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('graph_id', UUID(as_uuid=True), sa.ForeignKey('graphs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_type', sa.String(32), nullable=False),
        sa.Column('external_key', sa.String(1024), nullable=False),
        sa.Column('display_name', sa.String(512), nullable=False),
        sa.Column('workflow_file', sa.String(512), nullable=True),
        sa.Column('job_id', sa.String(255), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_graph_nodes_graph_id', 'graph_nodes', ['graph_id'])
    op.create_index('ix_graph_nodes_node_type', 'graph_nodes', ['node_type'])
    op.create_index('ix_graph_nodes_type_key', 'graph_nodes', ['graph_id', 'node_type', 'external_key'])

    op.create_table(
        'graph_edges',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('graph_id', UUID(as_uuid=True), sa.ForeignKey('graphs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_node_id', UUID(as_uuid=True), sa.ForeignKey('graph_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_node_id', UUID(as_uuid=True), sa.ForeignKey('graph_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('edge_type', sa.String(32), nullable=False),
        sa.Column('confidence', sa.String(16), nullable=False, server_default='certain'),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_graph_edges_graph_id', 'graph_edges', ['graph_id'])
    op.create_index('ix_graph_edges_graph_id_source', 'graph_edges', ['graph_id', 'source_node_id'])
    op.create_index('ix_graph_edges_graph_id_target', 'graph_edges', ['graph_id', 'target_node_id'])
    op.create_index('ix_graph_edges_edge_type', 'graph_edges', ['edge_type'])

def downgrade() -> None:
    op.drop_index('ix_graph_edges_edge_type', table_name='graph_edges')
    op.drop_index('ix_graph_edges_graph_id_target', table_name='graph_edges')
    op.drop_index('ix_graph_edges_graph_id_source', table_name='graph_edges')
    op.drop_index('ix_graph_edges_graph_id', table_name='graph_edges')
    op.drop_table('graph_edges')

    op.drop_index('ix_graph_nodes_type_key', table_name='graph_nodes')
    op.drop_index('ix_graph_nodes_node_type', table_name='graph_nodes')
    op.drop_index('ix_graph_nodes_graph_id', table_name='graph_nodes')
    op.drop_table('graph_nodes')

    op.drop_index('ix_graphs_status', table_name='graphs')
    op.drop_index('ix_graphs_graph_type', table_name='graphs')
    op.drop_index('ix_graphs_repo_name', table_name='graphs')
    op.drop_index('ix_graphs_org_login', table_name='graphs')
    op.drop_table('graphs')
