"""add upload_article join table

Revision ID: 1789ecea0eeb
Revises: c9ad553e1258
Create Date: 2026-04-26 20:59:37.131920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1789ecea0eeb'
down_revision: Union[str, Sequence[str], None] = 'c9ad553e1258'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'upload_article',
        sa.Column('upload_record_id', sa.String(), nullable=False),
        sa.Column('article_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['upload_record_id'], ['upload_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('upload_record_id', 'article_id'),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table('upload_article')
