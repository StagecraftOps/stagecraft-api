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
