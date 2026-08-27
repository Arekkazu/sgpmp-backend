"""test pipeline

Revision ID: 1c9659715a6d
Revises: 7e2d5f3bf17a
Create Date: 2026-08-27 12:30:43.064504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c9659715a6d'
down_revision: Union[str, Sequence[str], None] = '7e2d5f3bf17a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'usuario',
        sa.Column('test', sa.Text(), nullable=True),
        schema='modulo1'
    )


def downgrade() -> None:
    op.drop_column(
        'usuario',
        'test',
        schema='modulo1'
    )