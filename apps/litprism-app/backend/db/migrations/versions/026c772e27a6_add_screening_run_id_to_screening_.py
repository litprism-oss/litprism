"""add_screening_run_id_to_screening_results

Revision ID: 026c772e27a6
Revises: 1789ecea0eeb
Create Date: 2026-04-27 20:44:53.720130

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '026c772e27a6'
down_revision: Union[str, Sequence[str], None] = '1789ecea0eeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('screening_results') as batch_op:
        batch_op.add_column(sa.Column('screening_run_id', sa.String(), nullable=True))
        batch_op.create_foreign_key(
            'fk_screening_results_screening_run_id',
            'screening_runs',
            ['screening_run_id'], ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('screening_results') as batch_op:
        batch_op.drop_constraint('fk_screening_results_screening_run_id', type_='foreignkey')
        batch_op.drop_column('screening_run_id')
