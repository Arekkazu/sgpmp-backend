# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-150-G92 RF-62/RF-67: une los dos heads que dejó el merge de #733 |
"""Une los dos heads que dejó el merge de #733.

#733 trajo 8c4e2a6f1b93 → 4e7a1c9d2f60 (calidad de visión RF-62 e historial
diagnóstico inmutable RF-67) y f62b120bb13f (RLS de sensores), ambas sobre
517bee7b766c. `alembic upgrade head` falla con "Multiple head revisions" y el
workflow Deploy Migrations - dev quedó en rojo: dev está en f62b120bb13f sin
las otras dos. No se re-encadena f62b120bb13f porque ya está aplicada.

Revision ID: 30168ab97bd4
Revises: 4e7a1c9d2f60, f62b120bb13f
Create Date: 2026-10-25 23:50:58.176762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30168ab97bd4'
down_revision: Union[str, Sequence[str], None] = ('4e7a1c9d2f60', 'f62b120bb13f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
