from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        "workflow_runs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute("UPDATE workflow_runs SET updated_at = created_at")
    op.create_index(
        "ix_workflow_runs_org_login_repo_name", "workflow_runs", ["org_login", "repo_name"]
    )

    op.add_column(
        "organizations",
        sa.Column("sync_status", sa.String(32), nullable=False, server_default="pending"),
    )

def downgrade() -> None:
    op.drop_column("organizations", "sync_status")
    op.drop_index("ix_workflow_runs_org_login_repo_name", table_name="workflow_runs")
    op.drop_column("workflow_runs", "updated_at")
