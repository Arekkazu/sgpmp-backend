"""unificar heads de m02 tras rf35 rf36 rf49 y rf52

Sin cambios de esquema ni de datos. 6af637931784 ya había unido las heads de
fix/m02-fixes, pero después entraron #426 (RF-35), #431 (RF-36), #433 (RF-49)
y #437 (RF-52 E5), cada uno con su propia rama de migraciones. Con 4 heads,
`alembic upgrade head` falla; esta revisión las une sin tocar ninguna.

Revision ID: 8acca3af329a
Revises: 094d4799c3ca, 1ee808f9ee6b, 2848535f94f5, ccc0b8df02a6
Create Date: 2026-09-23 21:44:43.396140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8acca3af329a'
down_revision: Union[str, Sequence[str], None] = ('094d4799c3ca', '1ee808f9ee6b', '2848535f94f5', 'ccc0b8df02a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
