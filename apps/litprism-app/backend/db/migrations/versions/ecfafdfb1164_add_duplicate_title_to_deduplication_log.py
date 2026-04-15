"""add duplicate_title to deduplication_log

Revision ID: ecfafdfb1164
Revises: 9b41c7258fc3
Create Date: 2026-04-15 23:40:03.876473

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ecfafdfb1164"
down_revision: str | Sequence[str] | None = "9b41c7258fc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("deduplication_log") as batch_op:
        batch_op.add_column(sa.Column("duplicate_title", sa.Text(), nullable=True))
        batch_op.alter_column(
            "duplicate_article_id",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("deduplication_log") as batch_op:
        batch_op.alter_column(
            "duplicate_article_id",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )
        batch_op.drop_column("duplicate_title")
