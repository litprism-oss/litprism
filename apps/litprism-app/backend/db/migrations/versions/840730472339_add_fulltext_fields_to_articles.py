"""add fulltext fields to articles

Revision ID: 840730472339
Revises: 2d9abf7cbd77
Create Date: 2026-05-02 10:11:57.923859

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '840730472339'
down_revision: Union[str, Sequence[str], None] = '2d9abf7cbd77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('articles', sa.Column('fulltext_text', sa.Text(), nullable=True))
    op.add_column('articles', sa.Column('fulltext_source', sa.Text(), nullable=True))
    op.add_column('articles', sa.Column('fulltext_status', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('articles', 'fulltext_status')
    op.drop_column('articles', 'fulltext_source')
    op.drop_column('articles', 'fulltext_text')
