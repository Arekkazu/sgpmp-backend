"""add_detalle_tecnico_gap

Revision ID: add_detalle_tecnico_gap_before_rf37
Revises: 315eaa6c5dc1
Create Date: 2026-10-03 07:18:09.771955

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_detalle_tecnico_gap_before_rf37'
down_revision: Union[str, Sequence[str], None] = '315eaa6c5dc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
