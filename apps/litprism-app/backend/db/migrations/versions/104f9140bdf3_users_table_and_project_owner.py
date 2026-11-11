"""users table and project owner

Revision ID: 104f9140bdf3
Revises: 840730472339
Create Date: 2026-11-08 21:17:22.175109

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "104f9140bdf3"
down_revision: str | Sequence[str] | None = "840730472339"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    # Existing projects keep owner_id NULL until the bootstrap owner logs in.
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("owner_id", sa.String(), nullable=True))
        batch.create_index(op.f("ix_projects_owner_id"), ["owner_id"], unique=False)
        batch.create_foreign_key(
            "fk_projects_owner_id_users", "users", ["owner_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_projects_owner_id_users", type_="foreignkey")
        batch.drop_index(op.f("ix_projects_owner_id"))
        batch.drop_column("owner_id")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
