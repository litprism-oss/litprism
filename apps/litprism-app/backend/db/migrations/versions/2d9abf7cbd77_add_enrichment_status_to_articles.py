"""add enrichment_status to articles

Revision ID: 2d9abf7cbd77
Revises: 026c772e27a6
Create Date: 2026-04-29 21:00:26.527675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d9abf7cbd77'
down_revision: Union[str, Sequence[str], None] = '026c772e27a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('articles', sa.Column('enrichment_status', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('articles', 'enrichment_status')
