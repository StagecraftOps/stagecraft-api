"""Add remediations.suggested_yaml for suggestion-engine pivot.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-18

The worker no longer auto-creates PRs. Instead it stores Bedrock's suggested
fix in `suggested_yaml` (status becomes 'analyzed'). Users review and
optionally trigger a PR via POST /api/v1/remediations/{id}/raise-pr.
`fixed_yaml` is kept for backward compat but set to '' for new records.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("remediations", sa.Column("suggested_yaml", sa.Text(), nullable=True))
    op.alter_column("remediations", "fixed_yaml", server_default="")


def downgrade() -> None:
    op.drop_column("remediations", "suggested_yaml")
