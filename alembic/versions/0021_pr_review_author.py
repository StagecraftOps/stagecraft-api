from alembic import op
import sqlalchemy as sa

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('pr_reviews', sa.Column('author', sa.String(255), nullable=True))
    op.create_index('ix_pr_reviews_author', 'pr_reviews', ['author'])

def downgrade() -> None:
    op.drop_index('ix_pr_reviews_author', table_name='pr_reviews')
    op.drop_column('pr_reviews', 'author')
