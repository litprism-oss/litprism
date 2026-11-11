"""add benchmark_datasets.source

The first deploy of a7c1d2e3f4b5 created benchmark_datasets without this column; the
migration was edited afterwards, which databases that had already applied it never saw.
Add the column only if it is missing so both old and new databases end up the same.

Revision ID: b8d2e4f6a1c3
Revises: a7c1d2e3f4b5
Create Date: 2026-11-11 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d2e4f6a1c3"
down_revision: str | Sequence[str] | None = "a7c1d2e3f4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("benchmark_datasets")}
    if "source" not in cols:
        op.add_column("benchmark_datasets", sa.Column("source", sa.Text(), nullable=True))


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("benchmark_datasets")}
    if "source" in cols:
        op.drop_column("benchmark_datasets", "source")
