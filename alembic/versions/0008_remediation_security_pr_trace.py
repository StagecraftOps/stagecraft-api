"""Persist security findings, PR text, and agent trace on remediations

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-23

The multi-agent LangGraph pipeline (stagecraft-worker/app/agents/) already
computes security_risk_score, security_findings, pr_title, pr_description,
and agent_trace per analysis, but stagecraft-worker/app/tasks/remediation.py only
ever logged them and discarded them after the Celery task returned -- they
never reached the remediations row. This adds columns so that output
survives, instead of ~40% of what the agents figure out per run vanishing
on task completion.
"""
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
