"""merge_heads_rf32_unicidad_plantillas_y_migraciones_paralelas

Revision ID: 2c1e6bb33a79
Revises: a0aaa3d74844, f25c1cdae470
Create Date: 2026-09-06 00:08:39.778863

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c1e6bb33a79'
down_revision: Union[str, Sequence[str], None] = ('a0aaa3d74844', 'f25c1cdae470')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
