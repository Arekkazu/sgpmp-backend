"""merge_heads_rf09_rate_limiting_y_migraciones_paralelas

Revision ID: 52f259545ea8
Revises: 52b86f7385bd, 543cddec52a7, a1c3f6e0b2d4, b7d2a4f8e1c6, b7e19f07a038
Create Date: 2026-09-05 08:22:49.665645

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52f259545ea8'
down_revision: Union[str, Sequence[str], None] = ('52b86f7385bd', '543cddec52a7', 'a1c3f6e0b2d4', 'b7d2a4f8e1c6', 'b7e19f07a038')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
