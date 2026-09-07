"""merge_heads_intentos_fallidos_y_sensor

Revision ID: a78496a17479
Revises: 62e45ebdb323, 73d4c93a0961
Create Date: 2026-09-06 17:27:00.859357

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a78496a17479'
down_revision: Union[str, Sequence[str], None] = ('62e45ebdb323', '73d4c93a0961')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
