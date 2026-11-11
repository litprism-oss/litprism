"""add sources to search_runs

Revision ID: 1dec256fe3bf
Revises: 1c23407928e3
Create Date: 2026-04-19 15:15:23.524168

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1dec256fe3bf"
down_revision: str | Sequence[str] | None = "1c23407928e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "search_runs",
        sa.Column(
            "sources",
            sa.JSON(),
            nullable=False,
            server_default='["pubmed","europepmc","semanticscholar"]',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("search_runs", "sources")
