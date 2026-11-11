"""add upload_record_id to articles

Revision ID: c9ad553e1258
Revises: 1dec256fe3bf
Create Date: 2026-04-26 15:35:42.707723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9ad553e1258'
down_revision: Union[str, Sequence[str], None] = '1dec256fe3bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('articles', sa.Column('upload_record_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('articles', 'upload_record_id')
