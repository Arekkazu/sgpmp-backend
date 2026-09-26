"""merge_heads_fix_trigger_y_otra_migracion

Revision ID: 52b86f7385bd
Revises: 76567ec53021, f19e0ca62445
Create Date: 2026-09-04 21:52:17.971690

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52b86f7385bd'
down_revision: Union[str, Sequence[str], None] = ('76567ec53021', 'f19e0ca62445')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
