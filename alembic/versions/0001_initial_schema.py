from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("github_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("login", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(1024), nullable=False, server_default=""),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("github_org_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("login", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("webhook_secret", sa.String(255), nullable=False),
        sa.Column("webhook_id", sa.BigInteger(), nullable=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_organizations_owner_id", "organizations", ["owner_id"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("github_run_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("github_workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("org_login", sa.String(255), nullable=False),
        sa.Column("repo_name", sa.String(255), nullable=False),
        sa.Column("workflow_name", sa.String(512), nullable=False),
        sa.Column("workflow_file", sa.String(512), nullable=False),
        sa.Column("branch", sa.String(512), nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("conclusion", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("html_url", sa.String(1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_workflow_runs_org_login", "workflow_runs", ["org_login"])
    op.create_index("ix_workflow_runs_repo_name", "workflow_runs", ["repo_name"])
    op.create_index("ix_workflow_runs_conclusion", "workflow_runs", ["conclusion"])
    op.create_index("ix_workflow_runs_created_at", "workflow_runs", ["created_at"])

    op.create_table(
        "remediations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_login", sa.String(255), nullable=False),
        sa.Column("repo_name", sa.String(255), nullable=False),
        sa.Column("workflow_file", sa.String(512), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("fixed_yaml", sa.Text(), nullable=False),
        sa.Column("pr_url", sa.String(1024), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("pr_branch", sa.String(512), nullable=True),
        sa.Column("bedrock_model", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_remediations_org_login", "remediations", ["org_login"])
    op.create_index("ix_remediations_repo_name", "remediations", ["repo_name"])
    op.create_index("ix_remediations_status", "remediations", ["status"])

def downgrade() -> None:
    op.drop_table("remediations")
    op.drop_table("workflow_runs")
    op.drop_table("organizations")
    op.drop_table("users")
