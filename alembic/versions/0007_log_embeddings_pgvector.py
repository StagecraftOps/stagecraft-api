from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS log_embeddings (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_type      VARCHAR(32)  NOT NULL,
            source_id        UUID,
            org_login        VARCHAR(255),
            repo_name        VARCHAR(255),
            failure_category VARCHAR(64),
            chunk_text       TEXT         NOT NULL,
            embedding        vector(1024) NOT NULL,
            metadata         JSONB,
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_log_embeddings_source "
        "ON log_embeddings (source_type, source_id)"
    )

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS log_embeddings")

