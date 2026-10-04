"""merge current migration heads

Revision ID: e4772c889450
Revises: 4254acf5798b, add_detalle_tecnico_gap_before_rf37
Create Date: 2026-10-03 22:33:28.444416

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4772c889450'
down_revision: Union[str, Sequence[str], None] = ('4254acf5798b', 'add_detalle_tecnico_gap_before_rf37')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
