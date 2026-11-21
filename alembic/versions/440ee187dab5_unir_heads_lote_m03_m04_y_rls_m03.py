# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-29 | Arekkazu | RLS M03 RF-53..63: une el head del lote #831 con la RLS de modulo3 (#808) |
"""Une los dos heads que quedaron en dev tras mergear #831 y #808.

- fa8be230f1bf (#831): head del lote de fixes M03/M04 del 28-10.
- 0784d8c03206 (#808): RLS de las 18 tablas de modulo3 (ENABLE + FORCE, 63 políticas).

#808 se mergeó con ``down_revision = 'ebbb160365e5'`` mientras #831 ya había movido
el head a fa8be230f1bf, así que ``Deploy Migrations - dev`` se detuvo en la
validación de head único (DEV quedó en fa8be230f1bf, sin aplicar 0784d8c03206).
#808 solo crea políticas en modulo3 y ninguna revisión del lote toca políticas,
así que el orden entre ellas da igual.

Revision ID: 440ee187dab5
Revises: fa8be230f1bf, 0784d8c03206
Create Date: 2026-10-29 06:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '440ee187dab5'
down_revision: Union[str, Sequence[str], None] = ('fa8be230f1bf', '0784d8c03206')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
