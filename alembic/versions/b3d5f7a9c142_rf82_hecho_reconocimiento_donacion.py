# | Fecha      | Nombre         | Que se hizo                                                           |
# |------------|----------------|-----------------------------------------------------------------------|
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-302-G01 RF-82/RF-86: hecho contable propio para la donación    |
"""rf82: hecho contable RECONOCIMIENTO_DONACION para el reconocimiento de activos donados

Revision ID: b3d5f7a9c142
Revises: b7e2d94c1a68
Create Date: 2026-11-09

INC-M06-302-G01 (#989). Al confirmar el reconocimiento inicial de un activo con origen
DONACION el asiento acreditaba la cuenta del nacimiento: el catálogo cerrado de hechos de
RF-86 solo tenía ``RECONOCIMIENTO_NACIMIENTO`` y la donación lo reusaba, así que la matriz
contable (RF-109) no podía asignarle la cuenta «Ingreso por donación».

Se agrega ``RECONOCIMIENTO_DONACION`` a ``enum_linea_asiento_nic41_tipo_hecho`` (lo usan la
línea de asiento, la matriz y la corrección de líneas). El Contador asigna su par de cuentas
en Configuración contable; mientras no lo haga, la línea queda pendiente de cuenta, igual
que cualquier hecho sin asignación.

``downgrade`` no quita el valor: PostgreSQL no borra valores de un ENUM y las líneas ya
asentadas con él lo seguirían usando.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b3d5f7a9c142'
down_revision: Union[str, Sequence[str], None] = 'b7e2d94c1a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Un valor nuevo de enum no se puede usar en la misma transacción que lo crea.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE modulo6.enum_linea_asiento_nic41_tipo_hecho "
                   "ADD VALUE IF NOT EXISTS 'RECONOCIMIENTO_DONACION' AFTER 'RECONOCIMIENTO_NACIMIENTO'")


def downgrade() -> None:
    pass
