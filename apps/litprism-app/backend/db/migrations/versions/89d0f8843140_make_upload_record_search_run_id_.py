"""make upload_record search_run_id nullable

Revision ID: 89d0f8843140
Revises: ecfafdfb1164
Create Date: 2026-04-16 00:07:30.284872

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "89d0f8843140"
down_revision: str | Sequence[str] | None = "ecfafdfb1164"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("upload_records") as batch_op:
        batch_op.alter_column(
            "search_run_id",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("upload_records") as batch_op:
        batch_op.alter_column(
            "search_run_id",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )
