"""merge_heads_precision_umbrales_y_sincronizacion_edge

Revision ID: 58a6bfab5ce6
Revises: 1147428cd8fb, 424e8d205792
Create Date: 2026-09-18 14:43:41.016530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58a6bfab5ce6'
down_revision: Union[str, Sequence[str], None] = ('1147428cd8fb', '424e8d205792')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
