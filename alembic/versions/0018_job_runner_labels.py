"""Add runner_labels/runner_group_name to job_runs -- GitHub's Jobs API returns
these (e.g. labels=["ubuntu-latest"] or ["self-hosted","linux","x64"]) but
they were never synced, only the ephemeral runner_name -- which doesn't
distinguish runner type at all and is only ever populated once a runner is
actually assigned.

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-06
"""
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
