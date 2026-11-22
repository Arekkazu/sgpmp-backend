# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-18 | Arekkazu | M08 RF-103/RF-105: une el head de M08 con el de RF-93 de dev |
"""Une el head de M08 con el de dev.

d2e201924d1b (widgets del dashboard y ciclo de notificaciones, RF-103/RF-105) y
b8a323f06e9b (valor y referencia de la venta en la baja, RF-45/RF-93) cuelgan ambos de
f0d5920d51b6 y tocan objetos distintos (modulo9/notificaciones vs. modulo2), así que el
orden entre ellos da igual.

Revision ID: c8e1a7f30b52
Revises: d2e201924d1b, b8a323f06e9b
Create Date: 2026-11-18

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'c8e1a7f30b52'
down_revision: Union[str, Sequence[str], None] = ('d2e201924d1b', 'b8a323f06e9b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
