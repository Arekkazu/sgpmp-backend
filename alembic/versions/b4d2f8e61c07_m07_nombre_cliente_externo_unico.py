# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | INC-M07-373-G043 RF-101 FA-8: nombre de cliente externo único |
"""m07: nombre de cliente externo único, sin distinguir mayúsculas ni espacios (RF-101 FA-8)

Revision ID: b4d2f8e61c07
Revises: a7c3e91f5b20
Create Date: 2026-11-19

RF-101 define el ``nombre`` como único y FA-8 pide 409 al repetirlo. Hasta ahora solo eran únicos
``codigo`` e ``identificador_publico``. La aplicación lo valida antes de insertar; el índice cubre
dos registros simultáneos. Si ya hubiera nombres repetidos, el índice no se crea y la migración falla:
hay que renombrar uno antes (en TEST no hay, verificado el 2026-11-19).
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b4d2f8e61c07'
down_revision: Union[str, Sequence[str], None] = 'a7c3e91f5b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_cliente_externo_nombre
        ON modulo7.clientes_externos (lower(btrim(nombre)))
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS modulo7.uq_cliente_externo_nombre")
