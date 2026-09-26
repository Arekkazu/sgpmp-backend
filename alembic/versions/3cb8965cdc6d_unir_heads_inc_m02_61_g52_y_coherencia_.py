"""unir heads inc_m02_61_g52 y coherencia bitacora

Sin cambios de esquema ni de datos. #445 (1b9536d4411c) y #387 (6d8b88392ac8)
entraron a dev cada uno sobre su propia rama de migraciones; con 2 heads el
deploy de migraciones a DEV corta en "Verificar que existe una única head".

Revision ID: 3cb8965cdc6d
Revises: 1b9536d4411c, 6d8b88392ac8
Create Date: 2026-09-23 23:07:34.482354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3cb8965cdc6d'
down_revision: Union[str, Sequence[str], None] = ('1b9536d4411c', '6d8b88392ac8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
