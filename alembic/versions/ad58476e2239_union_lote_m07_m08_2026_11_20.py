# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-20 | Arekkazu | Lote M07/M08 RF-98/RF-102/RF-104: une las cuatro cabezas del lote |
"""Une las cabezas del lote M07/M08 del 20-11.

a7c3e91b2d40 (#1185, eventos del ciclo de vida del contrato), b4d2f8e61c07 (#1190, nombre único
del cliente externo), f11651020001 (#1191, archivo de la auditoría de integración) y a0701b636a92
(#1201, solo datos de notificaciones y panel) tocan objetos distintos, así que el orden entre
ellas da igual.

Revision ID: ad58476e2239
Revises: a7c3e91b2d40, b4d2f8e61c07, f11651020001, a0701b636a92
Create Date: 2026-11-20

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'ad58476e2239'
down_revision: Union[str, Sequence[str], None] = ('a7c3e91b2d40', 'b4d2f8e61c07', 'f11651020001', 'a0701b636a92')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
