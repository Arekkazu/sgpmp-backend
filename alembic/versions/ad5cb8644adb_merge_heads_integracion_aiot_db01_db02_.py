"""merge heads integracion aiot db01 db02 db03 db05 dev08

Revision ID: ad5cb8644adb
Revises: 4007369f8d3d, a9d4d253ac97, b0eb84a30467, e3b8c1d9f702
Create Date: 2026-10-19 22:02:42.086916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad5cb8644adb'
down_revision: Union[str, Sequence[str], None] = ('4007369f8d3d', 'a9d4d253ac97', 'b0eb84a30467', 'e3b8c1d9f702')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
